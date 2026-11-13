"""FastAPI server: API chat (SSE, kèm giọng nói) + phục vụ frontend tĩnh trong thư mục web/.

Chạy:  uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import base64
import functools
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .emotion_tags import EmotionTagParser, ParsedChunk
from .llm import ChatLLM, LLMError, make_llm
from .speech_text import SpeechSegmenter, clean_for_speech
from .tts import SpeechEngine, TTSError, make_tts
from .turn_log import TurnLog

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

log = logging.getLogger("waifu")

# Giới hạn số lượt gửi lên để request không phình mãi (trí nhớ dài hạn sẽ làm ở bước sau)
MAX_HISTORY = 40
MAX_MESSAGE_CHARS = 4000


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1)
    voice: bool = False

    @field_validator("messages")
    @classmethod
    def last_is_user(cls, v: list[ChatTurn]) -> list[ChatTurn]:
        if v[-1].role != "user":
            raise ValueError("message cuối phải là của user")
        return v


def trim_history(turns: list[ChatTurn]) -> list[dict[str, str]]:
    """Giữ MAX_HISTORY lượt gần nhất, và luôn bắt đầu bằng lượt user (yêu cầu của API)."""
    recent = turns[-MAX_HISTORY:]
    while recent and recent[0].role != "user":
        recent = recent[1:]
    return [t.model_dump() for t in recent]


@lru_cache
def get_llm() -> ChatLLM:
    return make_llm()


@lru_cache
def get_tts() -> SpeechEngine | None:
    return make_tts()


@lru_cache
def get_turn_log() -> TurnLog:
    return TurnLog(ROOT / "logs" / "turns.jsonl")


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def chunk_events(chunk: ParsedChunk) -> list[str]:
    events = [sse({"type": "emotion", "emotion": e}) for e in chunk.emotions]
    if chunk.text:
        events.append(sse({"type": "text", "text": chunk.text}))
    return events


def friendly_error(err: Exception) -> str:
    # Mỗi provider tự đổi lỗi của mình thành LLMError/TTSError; còn lại là lỗi ngoài dự kiến
    if isinstance(err, (LLMError, TTSError)):
        return str(err)
    return f"Có lỗi ngoài dự kiến: {err}. Xem log của server để biết chi tiết."


async def _warm_up_voice(tts: SpeechEngine) -> None:
    try:
        await asyncio.to_thread(tts.warm_up)
    except Exception:
        log.warning("nạp giọng lúc khởi động thất bại", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tts = get_tts()
    if tts is not None:
        # Nạp giọng nền lúc khởi động để lượt nói đầu không chậm thêm ~0,5s
        app.state.warm_up = asyncio.create_task(_warm_up_voice(tts))
    yield


app = FastAPI(title="Waifu Chat", lifespan=lifespan)


@app.get("/api/health")
async def health(llm: ChatLLM = Depends(get_llm), tts: SpeechEngine | None = Depends(get_tts)) -> dict:
    """`ok` = não đã sẵn sàng. Giọng có trạng thái riêng để thiếu giọng không chặn chat."""
    problem = await llm.check()
    if tts is None:
        voice = {"engine": None, "ok": False, "problem": "Giọng nói đang tắt (TTS_PROVIDER=none trong .env)."}
    else:
        voice_problem = tts.check()
        voice = {"engine": tts.name, "ok": voice_problem is None, "problem": voice_problem}
    return {"ok": problem is None, "provider": llm.provider, "model": llm.model, "problem": problem, "voice": voice}


FADE_IN_S = 0.01  # làm to dần 10ms ở đầu mỗi đoạn để không bật tiếng "tách"


def fade_in(pcm: bytes, rate: int) -> bytes:
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    n = min(len(samples), int(rate * FADE_IN_S))
    samples[:n] *= np.linspace(0.0, 1.0, n, dtype=np.float32)
    return samples.astype("<i2").tobytes()


async def iterate_in_thread(make_iter: Callable[[], Iterator[bytes]], stop: threading.Event) -> AsyncIterator[bytes]:
    """Chạy một iterator đồng bộ (engine giọng) trong thread, trả từng phần tử về event loop ngay khi có."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def put(item: tuple) -> None:
        try:
            loop.call_soon_threadsafe(queue.put_nowait, item)
        except RuntimeError:
            pass  # event loop đã đóng (server tắt)

    def run() -> None:
        try:
            for item in make_iter():
                if stop.is_set():
                    break
                put(("item", item))
            put(("end", None))
        except BaseException as err:
            put(("error", err))

    loop.run_in_executor(None, run)
    while True:
        kind, value = await queue.get()
        if kind == "item":
            yield value
        elif kind == "error":
            raise value
        else:
            return


class Speaker:
    """Worker nền: nhận đoạn chữ từ luồng LLM, tạo giọng trong thread và đẩy từng mảnh audio vào hàng đợi chung.

    Chạy song song nên chữ không phải chờ giọng (VieNeu mất ~0,45 giây cho mỗi giây audio).
    """

    def __init__(self, tts: SpeechEngine, out: asyncio.Queue) -> None:
        self.tts = tts
        self.out = out
        self.segmenter = SpeechSegmenter()
        self.seq = 0
        self.failed = False
        self.first_audio_at: float | None = None
        self._emotion: str | None = None  # cảm xúc đang có, chuyển sang đoạn sau
        self._pending: list[str] = []  # cảm xúc xuất hiện trong lúc gom đoạn hiện tại
        self._segments: asyncio.Queue[tuple[str, str | None] | None] = asyncio.Queue()
        self._stop = threading.Event()
        self._task = asyncio.create_task(self._run())

    def feed(self, chunk: ParsedChunk) -> None:
        self._pending += chunk.emotions
        self._enqueue(self.segmenter.push(chunk.text))

    async def finish(self) -> None:
        """Đọc nốt phần còn lại và chờ tạo xong hết giọng."""
        self._enqueue(self.segmenter.flush())
        self._segments.put_nowait(None)
        await self._task

    def cancel(self) -> None:
        self._stop.set()
        self._task.cancel()

    def _enqueue(self, segments: list[str]) -> None:
        for seg in segments:
            emotion = self._pending[0] if self._pending else self._emotion
            if self._pending:
                self._emotion = self._pending[-1]
                self._pending = []
            text = clean_for_speech(seg)
            if text:
                self._segments.put_nowait((text, emotion))

    async def _run(self) -> None:
        while (item := await self._segments.get()) is not None:
            if self.failed:
                continue
            text, emotion = item
            part = 0
            try:
                async for pcm in iterate_in_thread(functools.partial(self.tts.stream, text), self._stop):
                    self._emit(text, emotion, part, fade_in(pcm, self.tts.sample_rate) if part == 0 else pcm)
                    part += 1
                pause = int(self.tts.sample_rate * self.tts.segment_pause_s)
                if part and pause:
                    self._emit(text, emotion, part, bytes(2 * pause))
            except Exception as err:  # lỗi giọng không được làm hỏng phần chữ
                log.exception("tts failed")
                self.failed = True
                msg = str(err) if isinstance(err, TTSError) else f"Không tạo được giọng nói: {err}"
                self.out.put_nowait(sse({"type": "tts_error", "message": msg}))
            if part:
                self.seq += 1

    def _emit(self, text: str, emotion: str | None, part: int, pcm: bytes) -> None:
        if self.first_audio_at is None:
            self.first_audio_at = time.perf_counter()
        event = {"type": "audio", "seq": self.seq, "part": part, "rate": self.tts.sample_rate,
                 "pcm": base64.b64encode(pcm).decode("ascii")}
        if part == 0:
            event |= {"text": text, "emotion": emotion}
        self.out.put_nowait(sse(event))


@app.post("/api/chat")
async def chat(
    req: ChatRequest,
    llm: ChatLLM = Depends(get_llm),
    tts: SpeechEngine | None = Depends(get_tts),
    turn_log: TurnLog = Depends(get_turn_log),
) -> StreamingResponse:
    """Trả về SSE: emotion/text/audio ... rồi {type:"done", raw} hoặc {type:"error"}.

    `raw` là câu trả lời gốc còn tag; client lưu vào lịch sử để model giữ thói quen dùng tag.
    Chữ (từ LLM) và giọng (từ Speaker) cùng đẩy vào một hàng đợi; `done` chỉ gửi sau khi giọng đã tạo xong.
    """
    history = trim_history(req.messages)
    speak = req.voice and tts is not None

    async def events() -> AsyncIterator[str]:
        out: asyncio.Queue[str | None] = asyncio.Queue()
        speaker = Speaker(tts, out) if speak else None
        st = {"raw": [], "stop": "", "error": None, "first_text_at": None}
        start = time.perf_counter()

        async def produce() -> None:
            parser = EmotionTagParser()
            try:
                async for kind, value in llm.stream(history):
                    if kind != "text":
                        st["stop"] = value
                        continue
                    st["raw"].append(value)
                    chunk = parser.push(value)
                    if chunk.text.strip() and st["first_text_at"] is None:
                        st["first_text_at"] = time.perf_counter()
                    for ev in chunk_events(chunk):
                        out.put_nowait(ev)
                    if speaker:
                        speaker.feed(chunk)
                last = parser.flush()
                for ev in chunk_events(last):
                    out.put_nowait(ev)
                if st["stop"] == "refusal":
                    if speaker:
                        speaker.cancel()
                    st["error"] = "Nhân vật không trả lời được câu này (bị từ chối vì lý do an toàn)."
                    out.put_nowait(sse({"type": "error", "message": st["error"]}))
                    return
                final = {"raw": "".join(st["raw"]), "stopReason": st["stop"]}
                # Chữ xong rồi: client lưu lịch sử và cho gửi tin mới ngay, không phải chờ đọc hết giọng
                out.put_nowait(sse({"type": "text_done", **final}))
                if speaker:
                    speaker.feed(last)
                    await speaker.finish()
                out.put_nowait(sse({"type": "done", **final}))
            except Exception as err:  # báo lỗi cho người dùng thay vì cắt kết nối im lặng
                log.exception("chat failed")
                if speaker:
                    speaker.cancel()
                st["error"] = friendly_error(err)
                out.put_nowait(sse({"type": "error", "message": st["error"]}))
            finally:
                out.put_nowait(None)

        task = asyncio.create_task(produce())
        try:
            while (ev := await out.get()) is not None:
                yield ev
        finally:
            # Client ngắt kết nối thì dừng cả LLM lẫn giọng; lượt nào cũng được ghi log
            task.cancel()
            if speaker:
                speaker.cancel()

            def ms(at: float | None) -> int | None:
                return None if at is None else round((at - start) * 1000)

            turn_log.write({
                "provider": llm.provider, "model": llm.model, "tts": tts.name if speak else None,
                "first_text_ms": ms(st["first_text_at"]),
                "first_audio_ms": ms(speaker.first_audio_at if speaker else None),
                "total_ms": ms(time.perf_counter()), "segments": speaker.seq if speaker else 0,
                "chars": len("".join(st["raw"])), "stop": st["stop"] or None, "error": st["error"],
                "tts_error": bool(speaker and speaker.failed),
            })

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# Mount cuối cùng để không che các route /api
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
