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
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .emotion_tags import EmotionTagParser, ParsedChunk, parse_complete
from .episodes import EpisodeStore, make_episodes, render_episodes
from .llm import ChatLLM, LLMError, make_llm
from .memory import MemoryStore, make_memory, remember, system_prompt
from .presence import Presence, proactive_prompt
from .voice_style import VoiceStyle
from .wake import detect_wake, wake_settings
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
    turns_out: list[dict[str, str]] = []
    for t in recent:
        # Hai lượt liền nhau cùng vai (vd Mira chào rồi hỏi thăm khi anh chưa trả lời): gộp lại, vì Claude bắt buộc
        # user/assistant luân phiên
        if turns_out and turns_out[-1]["role"] == t.role:
            turns_out[-1]["content"] += "\n" + t.content
        else:
            turns_out.append(t.model_dump())
    if turns_out and turns_out[0]["role"] != "user":
        if len(recent) < len(turns):
            turns_out = turns_out[1:]  # bị cắt giữa chừng: bỏ lượt Mira mồ côi ở đầu như trước
        else:
            # Cả cuộc trò chuyện bắt đầu bằng lời Mira (chào khi mở trang): giữ lại để model biết mình đã hỏi gì,
            # thêm một lượt mở đầu ngắn cho đúng luân phiên
            turns_out.insert(0, {"role": "user", "content": "(anh mở trang)"})
    return turns_out


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
def get_presence() -> Presence:
    return Presence(ROOT / "data" / "presence.json")


@lru_cache
def get_episodes() -> EpisodeStore | None:
    return make_episodes(ROOT)


@lru_cache
def get_voice_style() -> VoiceStyle:
    return VoiceStyle()


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
    presence: Presence = Depends(get_presence),
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
            "voice": voice, "stt": ears,
            "proactive": {"greeting": presence.greeting, "checkin_minutes": presence.checkin_minutes},
            "wake": wake_settings()}


MIN_STT_SECONDS = 0.2
MAX_STT_SECONDS = 30


@app.post("/api/stt")
async def speech_to_text(
    request: Request,
    stt: SpeechRecognizer | None = Depends(get_stt),
    turn_log: TurnLog = Depends(get_turn_log),
) -> dict:
    """Body: PCM 16-bit LE mono 16kHz. Trả {text, wake, audio_ms, ms}; text rỗng nếu không nghe thấy tiếng nói.

    wake: câu mở đầu bằng tiếng gọi Mira (tên nghe nhầm được viết lại đúng trong text)."""
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
    wake, text = detect_wake(text)
    return {"text": text, "wake": wake, "audio_ms": round(seconds * 1000), "ms": took}


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

    def __init__(self, tts: SpeechEngine, out: asyncio.Queue, style: VoiceStyle | None = None) -> None:
        self.tts = tts
        self.out = out
        self.style = style
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
        # Tag cảm xúc là ranh giới: chữ trước tag đọc bằng cảm xúc cũ, câu đã xong thì cắt ngay
        pos = 0
        for at, emotion in chunk.marks:
            self._enqueue(self.segmenter.push(chunk.text[pos:at]))
            self._enqueue(self.segmenter.cut())
            self._pending.append(emotion)
            pos = at
        self._enqueue(self.segmenter.push(chunk.text[pos:]))

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
            spoken = text
            # Chỉ engine hiểu tín hiệu mới nhận "[cười]"; Piper sẽ đọc to nguyên chữ
            if self.style and getattr(self.tts, "supports_cues", False) and (cue := self.style.cue(emotion)):
                spoken = f"{cue} {text}"
            try:
                async for pcm in iterate_in_thread(functools.partial(self.tts.stream, spoken), self._stop):
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
            speed = self.style.speed_for(emotion) if self.style else 1.0
            if speed != 1.0:
                event["speed"] = speed  # trình duyệt phát nhanh/chậm hơn cả đoạn (kèm cao độ)
        self.out.put_nowait(sse(event))


def reply_stream(
    *,
    history: list[dict[str, str]],
    system: str,
    llm: ChatLLM,
    tts: SpeechEngine | None,
    speak: bool,
    turn_log: TurnLog,
    kind: str,
    after_text: Callable[[str], Awaitable[None]] | None = None,
    style: VoiceStyle | None = None,
) -> StreamingResponse:
    """SSE cho một lượt Mira nói: emotion/text/audio ... text_done ... rồi {type:"done", raw} hoặc {type:"error"}.

    Dùng chung cho tin của người dùng (/api/chat) và lời Mira tự nói (/api/proactive).
    Chữ (từ LLM) và giọng (từ Speaker) cùng đẩy vào một hàng đợi; `done` chỉ gửi sau khi giọng (và `after_text`,
    vd ghi nhớ) đã xong, để không bỏ task mồ côi.
    """

    async def events() -> AsyncIterator[str]:
        out: asyncio.Queue[str | None] = asyncio.Queue()
        speaker = Speaker(tts, out, style) if speak else None
        st = {"raw": [], "stop": "", "error": None, "first_text_at": None}
        start = time.perf_counter()

        async def produce() -> None:
            parser = EmotionTagParser()
            try:
                async for kind_, value in llm.stream(history, system=system):
                    if kind_ != "text":
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
                # Việc sau chữ (ghi nhớ, GPU) chạy song song với tạo giọng (CPU)
                extra = asyncio.create_task(after_text(final["raw"])) if after_text else None
                if speaker:
                    speaker.feed(last)
                    await speaker.finish()
                if extra:
                    await extra
                out.put_nowait(sse({"type": "done", **final}))
            except Exception as err:  # báo lỗi cho người dùng thay vì cắt kết nối im lặng
                log.exception("%s failed", kind)
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

            record = {
                "provider": llm.provider, "model": llm.model, "tts": tts.name if speak else None,
                "first_text_ms": ms(st["first_text_at"]),
                "first_audio_ms": ms(speaker.first_audio_at if speaker else None),
                "total_ms": ms(time.perf_counter()), "segments": speaker.seq if speaker else 0,
                "chars": len("".join(st["raw"])), "stop": st["stop"] or None, "error": st["error"],
                "tts_error": bool(speaker and speaker.failed),
            }
            if kind != "chat":
                record = {"kind": kind, **record}
            turn_log.write(record)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/api/chat")
async def chat(
    req: ChatRequest,
    llm: ChatLLM = Depends(get_llm),
    tts: SpeechEngine | None = Depends(get_tts),
    memory: MemoryStore | None = Depends(get_memory),
    presence: Presence = Depends(get_presence),
    turn_log: TurnLog = Depends(get_turn_log),
    style: VoiceStyle = Depends(get_voice_style),
    episodes: EpisodeStore | None = Depends(get_episodes),
) -> StreamingResponse:
    """Người dùng nói/gõ một tin. `raw` trong `done` là câu trả lời gốc còn tag để client lưu lịch sử."""
    now = datetime.now()  # giờ máy người dùng
    presence.user_spoke(now)
    user_message = req.messages[-1].content
    if episodes:
        if episodes.due(now):
            # Buổi trước chưa được tóm tắt (server vừa khởi động lại): làm ở nền, lượt này vẫn còn lịch sử bên trình duyệt
            schedule_episode_close(episodes, llm, turn_log)
        episodes.record("user", user_message, now)
    system = build_system(now, memory, episodes)

    async def after_reply(raw: str) -> None:
        if episodes:
            episodes.record("assistant", parse_complete(raw).text, datetime.now())
            episodes.close_later(llm, on_done=lambda r: turn_log.write({"kind": "episode", **r}))
        if memory:
            await update_memory()

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

    return reply_stream(
        history=trim_history(req.messages), system=system,
        llm=llm, tts=tts, speak=req.voice and tts is not None, turn_log=turn_log, kind="chat",
        after_text=after_reply, style=style,
    )


def build_system(now: datetime, memory: MemoryStore | None, episodes: EpisodeStore | None) -> str:
    if memory:
        memory.expire_events(now)  # bỏ sự kiện đã qua lâu trước khi đưa vào prompt
    return system_prompt(now, memory.facts() if memory else [],
                         render_episodes(episodes.list(), now) if episodes else "")


def schedule_episode_close(episodes: EpisodeStore, llm: ChatLLM, turn_log: TurnLog) -> asyncio.Task:
    async def run() -> None:
        try:
            turn_log.write({"kind": "episode", **(await episodes.close(llm))})
        except Exception as err:
            log.warning("tóm tắt buổi trò chuyện thất bại", exc_info=True)
            turn_log.write({"kind": "episode", "summarized": False, "error": type(err).__name__})

    return asyncio.create_task(run())


class ProactiveRequest(BaseModel):
    kind: Literal["greet", "checkin"]
    messages: list[ChatTurn] = Field(default_factory=list)
    voice: bool = False


@app.post("/api/proactive", response_model=None)
async def proactive(
    req: ProactiveRequest,
    llm: ChatLLM = Depends(get_llm),
    tts: SpeechEngine | None = Depends(get_tts),
    memory: MemoryStore | None = Depends(get_memory),
    presence: Presence = Depends(get_presence),
    turn_log: TurnLog = Depends(get_turn_log),
    style: VoiceStyle = Depends(get_voice_style),
    episodes: EpisodeStore | None = Depends(get_episodes),
) -> StreamingResponse | Response:
    """Mira tự nói: chào khi mở trang (`greet`) hoặc hỏi thăm khi im lâu (`checkin`). Chưa đến lúc thì trả 204.

    Lời nhắc cho model là một lượt "user" tạm: không hiện ra, không lưu lịch sử, không bị trích làm điều đáng nhớ.
    """
    now = datetime.now()
    due = presence.should_greet(now) if req.kind == "greet" else presence.should_check_in(now)
    if not due:
        return Response(status_code=204)
    if req.kind == "greet":
        presence.greeted(now)  # đánh dấu ngay để tải lại trang liên tục không chào nhiều lần
    if episodes and episodes.due(now):
        # Lời chào là lúc tóm tắt buổi trước có ích nhất ("hôm qua anh kể..."): chờ xong rồi mới chào (~1,5s)
        await schedule_episode_close(episodes, llm, turn_log)
    note = ChatTurn(role="user", content=proactive_prompt(req.kind, presence.last_user_at, now))

    async def after_reply(raw: str) -> None:
        if episodes:  # lời Mira tự nói cũng là một phần buổi trò chuyện (lời nhắc ẩn thì không)
            episodes.record("assistant", parse_complete(raw).text, datetime.now())

    return reply_stream(
        history=trim_history([*req.messages, note]), system=build_system(now, memory, episodes),
        llm=llm, tts=tts, speak=req.voice and tts is not None, turn_log=turn_log, kind=req.kind, style=style,
        after_text=after_reply,
    )


@app.get("/api/memory")
def list_memory(
    memory: MemoryStore | None = Depends(get_memory),
    episodes: EpisodeStore | None = Depends(get_episodes),
) -> dict:
    """Những điều Mira nhớ về người dùng và tóm tắt các buổi trò chuyện (để xem/xóa trên giao diện)."""
    if memory is None:
        return {"enabled": False, "facts": [], "episodes": []}
    return {"enabled": True, "facts": [f.__dict__ for f in memory.facts()],
            "episodes": [e.__dict__ for e in reversed(episodes.list())] if episodes else []}


@app.delete("/api/memory/episodes/{episode_id}")
def forget_episode(episode_id: str, episodes: EpisodeStore | None = Depends(get_episodes)) -> dict:
    if episodes is None or not episodes.delete(episode_id):
        raise HTTPException(404, "Không tìm thấy buổi trò chuyện này.")
    return {"ok": True}


@app.delete("/api/memory/{fact_id}")
def forget_fact(fact_id: str, memory: MemoryStore | None = Depends(get_memory)) -> dict:
    if memory is None or not memory.delete(fact_id):
        raise HTTPException(404, "Không tìm thấy điều này trong trí nhớ.")
    return {"ok": True}


@app.delete("/api/memory")
def forget_all(
    memory: MemoryStore | None = Depends(get_memory),
    episodes: EpisodeStore | None = Depends(get_episodes),
) -> dict:
    if memory is not None:
        memory.clear()
    if episodes is not None:
        episodes.clear()
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
