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
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .emotion_tags import EmotionTagParser, ParsedChunk
from .llm import ChatLLM, LLMError, make_llm
from .memory import MemoryStore, make_memory, remember, system_prompt
from .speech_text import SpeechSegmenter, clean_for_speech
from .stt import SAMPLE_RATE, SpeechRecognizer, STTError, make_stt
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


# Ollama chạy ngữ cảnh 4096 token và tự cắt phần đầu (gồm cả persona) khi vượt. Tiếng Việt ~2,1 ký tự/token:
# system + ngày ~400 token, trí nhớ ≤ ~570, trả lời 512 -> lịch sử ≤ ~5000 ký tự (specs/004-long-term-memory/plan.md)
HISTORY_CHAR_BUDGET = 5000


def trim_history(turns: list[ChatTurn], char_budget: int = HISTORY_CHAR_BUDGET) -> list[dict[str, str]]:
    """Giữ các lượt gần nhất trong giới hạn MAX_HISTORY và ngân sách ký tự; luôn bắt đầu bằng lượt user."""
    recent: list[ChatTurn] = []
    used = 0
    for turn in reversed(turns[-MAX_HISTORY:]):
        if recent and used + len(turn.content) > char_budget:
            break  # lượt cuối (tin vừa gửi) luôn được giữ
        recent.insert(0, turn)
        used += len(turn.content)
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
def get_stt() -> SpeechRecognizer | None:
    return make_stt()


@lru_cache
def get_memory() -> MemoryStore | None:
    return make_memory(ROOT)


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


async def _warm_up(label: str, engine: SpeechEngine | SpeechRecognizer) -> None:
    try:
        await asyncio.to_thread(engine.warm_up)
    except Exception:
        log.warning("nạp %s lúc khởi động thất bại", label, exc_info=True)


_llm_warming: set[asyncio.Task] = set()  # giữ tham chiếu để task nền không bị dọn giữa chừng


def warm_llm_in_background(llm: ChatLLM) -> None:
    """Nạp sẵn "não" ở nền (gọi lúc khởi động và mỗi lần mở trang); đang nạp thì không gọi thêm."""
    if _llm_warming:
        return

    async def run() -> None:
        started = time.perf_counter()
        try:
            await llm.warm_up()
            log.info("nạp sẵn %s mất %.1fs", llm.model, time.perf_counter() - started)
        except Exception:
            log.warning("nạp sẵn %s thất bại", llm.model, exc_info=True)  # /api/health sẽ báo lỗi rõ cho người dùng

    task = asyncio.create_task(run())
    _llm_warming.add(task)
    task.add_done_callback(_llm_warming.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Nạp sẵn giọng (VieNeu ~8s) và tai (Whisper ~2s) ở nền để lượt nói/nghe đầu không bị chậm
    app.state.warm_ups = [
        asyncio.create_task(_warm_up(label, engine))
        for label, engine in (("giọng", get_tts()), ("tai", get_stt()))
        if engine is not None
    ]
    warm_llm_in_background(get_llm())
    yield


app = FastAPI(title="Mira – 3D Vietnamese Voice Companion", lifespan=lifespan)


@app.get("/api/health")
async def health(
    llm: ChatLLM = Depends(get_llm),
    tts: SpeechEngine | None = Depends(get_tts),
    stt: SpeechRecognizer | None = Depends(get_stt),
) -> dict:
    """`ok` = não đã sẵn sàng. Giọng và tai có trạng thái riêng để thiếu chúng không chặn chat."""
    problem = await llm.check()
    if problem is None:
        warm_llm_in_background(llm)  # trang vừa mở: nạp model ngay, để câu đầu không phải chờ
    if tts is None:
        voice = {"engine": None, "ok": False, "problem": "Giọng nói đang tắt (TTS_PROVIDER=none trong .env)."}
    else:
        voice_problem = tts.check()
        voice = {"engine": tts.name, "ok": voice_problem is None, "problem": voice_problem}
    if stt is None:
        ears = {"engine": None, "ok": False, "problem": "Nghe giọng nói đang tắt (STT_PROVIDER=none trong .env)."}
    else:
        stt_problem = stt.check()
        ears = {"engine": stt.name, **stt.info(), "ok": stt_problem is None, "problem": stt_problem}
    return {"ok": problem is None, "provider": llm.provider, "model": llm.model, "problem": problem,
            "voice": voice, "stt": ears}


MIN_STT_SECONDS = 0.2
MAX_STT_SECONDS = 30


@app.post("/api/stt")
async def speech_to_text(
    request: Request,
    stt: SpeechRecognizer | None = Depends(get_stt),
    turn_log: TurnLog = Depends(get_turn_log),
) -> dict:
    """Body: PCM 16-bit LE mono 16kHz. Trả {text, audio_ms, ms}; text rỗng nếu không nghe thấy tiếng nói."""
    if stt is None:
        raise HTTPException(503, "Nghe giọng nói đang tắt (STT_PROVIDER=none trong .env).")
    pcm = await request.body()
    if len(pcm) % 2:
        raise HTTPException(400, "Dữ liệu âm thanh hỏng (số byte lẻ).")
    seconds = len(pcm) / 2 / SAMPLE_RATE
    if seconds < MIN_STT_SECONDS:
        raise HTTPException(400, "Đoạn ghi âm quá ngắn, giữ nút lâu hơn chút nha.")
    if seconds > MAX_STT_SECONDS:
        raise HTTPException(413, f"Đoạn ghi âm dài quá {MAX_STT_SECONDS} giây, nói ngắn lại chút nha.")
    start = time.perf_counter()
    error = None
    text = ""
    try:
        text = await asyncio.to_thread(stt.transcribe, pcm)
    except Exception as err:
        log.exception("stt failed")
        error = str(err) if isinstance(err, STTError) else f"Không nhận dạng được giọng nói: {err}"
    took = round((time.perf_counter() - start) * 1000)
    # Không lưu âm thanh hay nội dung, chỉ độ dài và thời gian xử lý
    turn_log.write({"kind": "stt", "engine": stt.name, "audio_ms": round(seconds * 1000), "ms": took,
                    "chars": len(text), "error": error})
    if error:
        raise HTTPException(500, error)
    return {"text": text, "audio_ms": round(seconds * 1000), "ms": took}


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
    memory: MemoryStore | None = Depends(get_memory),
    turn_log: TurnLog = Depends(get_turn_log),
) -> StreamingResponse:
    """Trả về SSE: emotion/text/audio ... rồi {type:"done", raw} hoặc {type:"error"}.

    `raw` là câu trả lời gốc còn tag; client lưu vào lịch sử để model giữ thói quen dùng tag.
    Chữ (từ LLM) và giọng (từ Speaker) cùng đẩy vào một hàng đợi; `done` chỉ gửi sau khi giọng đã tạo xong.
    """
    history = trim_history(req.messages)
    speak = req.voice and tts is not None
    now = datetime.now()  # giờ máy người dùng
    system = system_prompt(now, memory.facts() if memory else [])
    user_message = req.messages[-1].content

    async def update_memory() -> None:
        """Trích điều đáng nhớ từ tin vừa gửi. Lỗi ở đây chỉ ghi log, không bao giờ làm hỏng lượt chat."""
        started = time.perf_counter()
        record: dict = {"kind": "memory", "added": 0, "replaced": 0, "error": None}
        try:
            record |= await remember(llm, memory, user_message, now)
        except Exception as err:
            log.warning("cập nhật trí nhớ thất bại", exc_info=True)
            record["error"] = type(err).__name__
        record["ms"] = round((time.perf_counter() - started) * 1000)
        turn_log.write(record)

    async def events() -> AsyncIterator[str]:
        out: asyncio.Queue[str | None] = asyncio.Queue()
        speaker = Speaker(tts, out) if speak else None
        st = {"raw": [], "stop": "", "error": None, "first_text_at": None}
        start = time.perf_counter()

        async def produce() -> None:
            parser = EmotionTagParser()
            try:
                async for kind, value in llm.stream(history, system=system):
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
                # Ghi nhớ chạy song song với tạo giọng (GPU vs CPU); `done` chờ cả hai để không bỏ task mồ côi
                remembering = asyncio.create_task(update_memory()) if memory else None
                if speaker:
                    speaker.feed(last)
                    await speaker.finish()
                if remembering:
                    await remembering
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


@app.get("/api/memory")
def list_memory(memory: MemoryStore | None = Depends(get_memory)) -> dict:
    """Những điều Mira nhớ về người dùng (để xem/xóa trên giao diện)."""
    if memory is None:
        return {"enabled": False, "facts": []}
    return {"enabled": True, "facts": [f.__dict__ for f in memory.facts()]}


@app.delete("/api/memory/{fact_id}")
def forget_fact(fact_id: str, memory: MemoryStore | None = Depends(get_memory)) -> dict:
    if memory is None or not memory.delete(fact_id):
        raise HTTPException(404, "Không tìm thấy điều này trong trí nhớ.")
    return {"ok": True}


@app.delete("/api/memory")
def forget_all(memory: MemoryStore | None = Depends(get_memory)) -> dict:
    if memory is not None:
        memory.clear()
    return {"ok": True}


# Mount cuối cùng để không che các route /api
@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    # Không có header này thì trình duyệt tự đoán file còn mới và dùng bản cũ sau khi cập nhật app.
    # no-cache = vẫn lưu nhưng hỏi lại server mỗi lần; file không đổi thì server trả 304 (theo ETag), gần như không tốn gì.
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
