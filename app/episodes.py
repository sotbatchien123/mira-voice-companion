"""Tóm tắt các buổi trò chuyện cũ (spec 009), để Mira nhớ "hôm trước mình nói chuyện gì".

Server tự ghi lại buổi đang nói (data/episodes.json, không vào git). Anh im quá EPISODE_GAP_MINUTES thì nhờ model tóm
tắt buổi đó thành 1–3 câu; system prompt kèm vài bản tóm tắt gần nhất. Lịch sử chat bên trình duyệt có thể bị xóa hoặc
bị cắt cho vừa ngữ cảnh, nên không dựa vào nó.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .memory import event_status, part_of_day, resolve_relative_dates

log = logging.getLogger("waifu")

MAX_EPISODES = 20
PROMPT_EPISODES = 3
EPISODE_PROMPT_CHARS = 700
MAX_SESSION_CHARS = 6000  # phần đưa model tóm tắt: buổi quá dài thì giữ đoạn cuối
MAX_SUMMARY_CHARS = 400
MIN_USER_CHARS = 30  # buổi chỉ có "chào em" thì không có gì để tóm tắt


@dataclass
class Episode:
    id: str
    date: str  # yyyy-mm-dd của lúc buổi trò chuyện bắt đầu
    started: str  # giờ bắt đầu hh:mm
    summary: str


@dataclass
class PendingClose:
    """Bản chụp buổi đang nói, chờ model tóm tắt (EpisodeStore.take_session)."""
    turns: list[tuple[str, str]]
    started: str | None
    generation: int


SUMMARY_PROMPT = """Đây là một buổi trò chuyện giữa anh (người dùng) và Mira (bạn đồng hành AI).
Tóm tắt lại trong 1 đến 3 câu ngắn để lần sau Mira nhớ hai người đã nói gì.

Quy tắc:
- Viết ở ngôi thứ ba: "Anh kể...", "Mira hỏi...".
- Chỉ giữ ý chính: anh kể chuyện gì, anh định làm gì, hai người hẹn gì. Bỏ câu chào, câu khen xã giao.
- Giữ tên riêng (người, nơi, công ty, thú cưng).
- Mốc thời gian viết đủ như "ngày mai", "hôm qua", "thứ Sáu này", "thứ Bảy tuần sau"; không viết tắt "mai",
  không tự đổi sang ngày.
- Chỉ dùng điều có trong cuộc trò chuyện. Không suy đoán, không thêm chi tiết.

CUỘC TRÒ CHUYỆN:
{dialog}

Trả về JSON đúng dạng: {{"tom_tat": "..."}}"""


def summary_messages(turns: list[tuple[str, str]]) -> list[dict[str, str]]:
    lines = [f"{'Anh' if role == 'user' else 'Mira'}: {text}" for role, text in turns]
    dialog = "\n".join(lines)
    if len(dialog) > MAX_SESSION_CHARS:
        dialog = "...\n" + dialog[-MAX_SESSION_CHARS:]
    return [{"role": "user", "content": SUMMARY_PROMPT.format(dialog=dialog)}]


def parse_summary(raw: str) -> str:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return ""
    text = data.get("tom_tat") if isinstance(data, dict) else None
    return " ".join(str(text or "").split())[:MAX_SUMMARY_CHARS]


def _ago(day: datetime, today: datetime) -> str:
    ago = (today.date() - day.date()).days
    if ago <= 0:
        return "hôm nay"
    if ago == 1:
        return "hôm qua"
    return f"{ago} ngày trước"


def render_episodes(episodes: list[Episode], today: datetime, limit: int = EPISODE_PROMPT_CHARS) -> str:
    """Vài buổi gần nhất, mới nhất trước. Ngày tương đối trong tóm tắt ("mai") đổi thành ngày cụ thể như trí nhớ."""
    lines, used = [], 0
    for ep in reversed(episodes[-PROMPT_EPISODES:]):
        day = datetime.strptime(f"{ep.date} {ep.started}", "%Y-%m-%d %H:%M")
        text = resolve_relative_dates(ep.summary, ep.date)
        line = f"- {_ago(day, today)} ({part_of_day(day)} {day:%d/%m}): {text}{event_status(text, today)}"
        if used + len(line) > limit:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


class EpisodeStore:
    """Buổi đang nói + các bản tóm tắt. Ghi nguyên tử như MemoryStore."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.gap = timedelta(minutes=_minutes("EPISODE_GAP_MINUTES", 30))
        self.episodes: list[Episode] = []
        self.started: str | None = None  # iso, lúc buổi đang nói bắt đầu
        self.last_at: str | None = None  # iso, lượt gần nhất của buổi đang nói
        self.turns: list[tuple[str, str]] = []
        self._summarizing = False
        self._generation = 0  # tăng mỗi lần clear(): bản tóm tắt làm dở từ trước lúc xóa thì bỏ đi
        self._timer: asyncio.Task | None = None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.episodes = [Episode(**e) for e in raw.get("episodes", [])]
            cur = raw.get("current") or {}
            self.started, self.last_at = cur.get("started"), cur.get("last_at")
            self.turns = [(t[0], t[1]) for t in cur.get("turns", [])]
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, AttributeError, IndexError):
            path.replace(path.with_suffix(path.suffix + ".bad"))  # để còn cứu tay, đừng để lần ghi sau đè mất
            log.warning("file %s hỏng, cất bản hỏng ra .bad rồi bắt đầu lại", path)
            self.episodes, self.started, self.last_at, self.turns = [], None, None, []

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"episodes": [asdict(e) for e in self.episodes],
                "current": {"started": self.started, "last_at": self.last_at, "turns": [list(t) for t in self.turns]}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[Episode]:
        with self._lock:
            return list(self.episodes)

    def record(self, role: str, text: str, now: datetime) -> None:
        """Ghi một lượt vào buổi đang nói (chữ đã bỏ tag cảm xúc)."""
        text = " ".join(text.split())
        if not text:
            return
        with self._lock:
            if self.started is None:
                self.started = now.isoformat(timespec="minutes")
            self.last_at = now.isoformat(timespec="minutes")
            self.turns.append((role, text))
            self._write()

    def due(self, now: datetime) -> bool:
        """Buổi đang nói đã kết thúc (im quá lâu) mà chưa được tóm tắt."""
        with self._lock:
            if not self.turns or self.last_at is None:
                return False
            return now - datetime.fromisoformat(self.last_at) >= self.gap

    def take_session(self) -> PendingClose | None:
        """Chụp lại buổi đang nói để tóm tắt (đồng bộ). None nếu không có gì hoặc đang tóm tắt dở.

        Phải gọi TRƯỚC khi ghi lượt mới: `asyncio.create_task(close())` chưa chạy ngay, nên lượt ghi ngay sau đó sẽ lọt
        vào bản chụp và bị tóm tắt vào buổi cũ. Đã nhận bản chụp thì phải gọi `summarize()` (nó mở khóa tóm tắt)."""
        with self._lock:
            if self._summarizing or not self.turns:
                return None
            self._summarizing = True
            return PendingClose(list(self.turns), self.started, self._generation)

    async def close(self, llm) -> dict:
        """Tóm tắt buổi đang nói và mở buổi mới. Trả số liệu cho log (không có nội dung)."""
        return await self.summarize(self.take_session(), llm)

    async def summarize(self, pending: PendingClose | None, llm) -> dict:
        if pending is None:
            return {"summarized": False}
        turns, started = pending.turns, pending.started
        try:
            user_chars = sum(len(t) for r, t in turns if r == "user")
            summary = ""
            if user_chars >= MIN_USER_CHARS:
                summary = parse_summary(await llm.complete(summary_messages(turns), json_mode=True, max_tokens=300))
                if not summary:  # model trả sai dạng: giữ buổi lại, lần im sau thử tóm tắt lại
                    return {"summarized": False, "turns": len(turns), "error": "bad_summary"}
            with self._lock:
                if self._generation != pending.generation:
                    # Anh đã bấm "Quên hết" trong lúc chờ model: không ghi lại buổi đã xóa, không đụng lượt nói sau đó
                    return {"summarized": False, "turns": len(turns), "cleared": True}
                if summary and started:
                    begin = datetime.fromisoformat(started)
                    self.episodes.append(Episode(uuid.uuid4().hex[:8], f"{begin:%Y-%m-%d}", f"{begin:%H:%M}", summary))
                    self.episodes = self.episodes[-MAX_EPISODES:]
                # Bỏ đúng các lượt đã tóm tắt; lượt mới chen vào trong lúc chờ model thì giữ lại
                self.turns = self.turns[len(turns):]
                self.started = self.last_at if self.turns else None
                if not self.turns:
                    self.last_at = None
                self._write()
            return {"summarized": bool(summary), "turns": len(turns)}
        finally:
            with self._lock:
                self._summarizing = False

    def close_later(self, llm, on_done=None) -> None:
        """Hẹn tóm tắt sau khoảng im: anh quay lại thì bản tóm tắt đã sẵn. Có lượt mới thì hẹn lại từ đầu.

        Server tắt giữa chừng thì lần sau `due()` bắt được và tóm tắt ngay.
        """
        if self._timer is not None:
            self._timer.cancel()

        async def wait_then_close() -> None:
            await asyncio.sleep(self.gap.total_seconds())
            try:
                result = await self.close(llm)
                if on_done:
                    on_done(result)
            except Exception:
                log.warning("tóm tắt buổi trò chuyện thất bại", exc_info=True)

        self._timer = asyncio.create_task(wait_then_close())

    def delete(self, episode_id: str) -> bool:
        with self._lock:
            before = len(self.episodes)
            self.episodes = [e for e in self.episodes if e.id != episode_id]
            changed = len(self.episodes) != before
            if changed:
                self._write()
            return changed

    def clear(self) -> None:
        with self._lock:
            self.episodes, self.turns, self.started, self.last_at = [], [], None, None
            self._generation += 1
            self._write()


def _minutes(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def make_episodes(root: Path) -> EpisodeStore | None:
    if os.getenv("MEMORY_ENABLED", "true").strip().lower() in ("false", "0", "off", "no"):
        return None
    return EpisodeStore(root / "data" / "episodes.json")
