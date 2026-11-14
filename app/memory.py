"""Trí nhớ dài hạn của Mira: những điều người dùng kể về bản thân, lưu ở máy (data/memory.json).

Model chỉ ĐỀ XUẤT điều mới kèm loại; việc thay/xóa do code quyết định theo luật cố định. Spike (spikes/memory_extract.py):
cho model 8B tự chọn điều cũ để xóa thì nó xóa bừa cả điều không liên quan; nhờ model tính ngày thì tính sai.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .persona import SYSTEM_PROMPT

log = logging.getLogger("waifu")

KINDS = ("ten", "tuoi", "nghe_nghiep", "noi_o", "cach_goi", "gia_dinh", "thu_cung", "so_thich", "khong_thich",
         "suc_khoe", "su_kien", "khac")
SINGLE_VALUE = {"ten", "tuoi", "nghe_nghiep", "noi_o", "cach_goi"}  # điều mới thay điều cũ cùng loại
MAX_FACTS = 60
MAX_FACT_CHARS = 200
EVENT_KEEP_DAYS = 14  # sự kiện có ngày cụ thể đã qua quá chừng này ngày thì bỏ (không còn đáng hỏi thăm)
MEMORY_PROMPT_CHARS = 1200  # ~570 token tiếng Việt, xem specs/004-long-term-memory/plan.md
WEEKDAYS = ("thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật")


@dataclass
class Fact:
    id: str
    kind: str
    text: str
    said_on: str  # yyyy-mm-dd, ngày người dùng nói (code ghi, không nhờ model)


def _norm(text: str) -> str:
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFC", text).lower()).strip()


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._facts = self._read()

    def _read(self) -> list[Fact]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [Fact(**f) for f in raw.get("facts", [])]
        except FileNotFoundError:
            return []
        except (ValueError, TypeError, AttributeError):
            log.warning("file trí nhớ %s hỏng, bắt đầu lại rỗng", self.path)  # không chặn app
            return []

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"facts": [asdict(f) for f in self._facts]}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(self.path)  # ghi nguyên tử: tắt máy giữa chừng không làm hỏng file

    def facts(self) -> list[Fact]:
        with self._lock:
            return list(self._facts)

    def add(self, items: list[tuple[str, str]], said_on: str) -> dict:
        """Thêm (loại, câu). Trả {added, replaced} để ghi log (không có nội dung)."""
        added = replaced = 0
        with self._lock:
            for kind, text in items:
                if any(_norm(f.text) == _norm(text) for f in self._facts):
                    continue
                if kind in SINGLE_VALUE:
                    before = len(self._facts)
                    self._facts = [f for f in self._facts if f.kind != kind]
                    replaced += before - len(self._facts)
                self._facts.append(Fact(uuid.uuid4().hex[:8], kind, text, said_on))
                added += 1
            if len(self._facts) > MAX_FACTS:
                # bỏ điều cũ nhất, nhưng giữ các điều cơ bản (tên, tuổi, nghề...)
                extra = len(self._facts) - MAX_FACTS
                keep = []
                for f in self._facts:
                    if extra and f.kind not in SINGLE_VALUE:
                        extra -= 1
                        continue
                    keep.append(f)
                self._facts = keep
            if added or replaced:
                self._write()
        return {"added": added, "replaced": replaced}

    def delete(self, fact_id: str) -> bool:
        with self._lock:
            before = len(self._facts)
            self._facts = [f for f in self._facts if f.id != fact_id]
            changed = len(self._facts) != before
            if changed:
                self._write()
            return changed

    def clear(self) -> None:
        with self._lock:
            self._facts = []
            self._write()

    def expire_events(self, today: datetime, keep_days: int | None = None) -> int:
        """Bỏ sự kiện đã qua lâu ("thứ Sáu này anh đi phỏng vấn" sau 2 tuần). Luật cố định trong code, không nhờ model.

        Chỉ bỏ điều loại su_kien có ngày cụ thể (sau khi đổi mốc tương đối) và mọi ngày trong đó đều đã qua quá
        keep_days. Sự kiện không có ngày thì giữ (sẽ bị đẩy ra khi đầy MAX_FACTS)."""
        keep = EVENT_KEEP_DAYS if keep_days is None else keep_days
        cutoff = today.date() - timedelta(days=keep)

        def stale(f: Fact) -> bool:
            if f.kind != "su_kien":
                return False
            dates = _dates(resolve_relative_dates(f.text, f.said_on))
            return bool(dates) and max(dates) < cutoff

        with self._lock:
            before = len(self._facts)
            self._facts = [f for f in self._facts if not stale(f)]
            removed = before - len(self._facts)
            if removed:
                self._write()
            return removed


def part_of_day(now: datetime) -> str:
    """Ghi rõ buổi: spike cho thấy chỉ có giờ thì model 8B nói "trưa rồi" lúc 15:00."""
    h = now.hour
    if 4 <= h < 10:
        return "buổi sáng"
    if 10 <= h < 13:
        return "buổi trưa"
    if 13 <= h < 18:
        return "buổi chiều"
    if 18 <= h < 22:
        return "buổi tối"
    return "đêm khuya"


def today_line(now: datetime) -> str:
    return f"Bây giờ là {now:%H:%M} ({part_of_day(now)}), {WEEKDAYS[now.weekday()]} ngày {now:%d/%m/%Y}."


_DAY_NAMES = {"hai": 0, "ba": 1, "tư": 2, "năm": 3, "sáu": 4, "bảy": 5}
_WEEKDAY_RE = re.compile(r"(thứ (hai|ba|tư|năm|sáu|bảy)|chủ nhật) (tuần sau|tuần tới|này)", re.IGNORECASE)
_SIMPLE_DAYS = {"hôm kia": -2, "hôm qua": -1, "hôm nay": 0, "ngày mai": 1, "ngày kia": 2, "ngày mốt": 2}
_SIMPLE_RE = re.compile("|".join(_SIMPLE_DAYS), re.IGNORECASE)
_NEXT_WEEK_RE = re.compile(r"tuần (sau|tới)", re.IGNORECASE)


def resolve_relative_dates(text: str, said_on: str) -> str:
    """Đổi "ngày mai", "hôm qua", "thứ Bảy tuần sau"... thành ngày cụ thể, tính từ ngày anh nói.

    Đo thật: dù prompt ghi "anh nói 2 ngày trước", model 8B vẫn hỏi "hôm nay anh đi phỏng vấn à?" cho một sự kiện
    "ngày mai" đã qua. Cộng trừ ngày là việc của code, không phải của model."""
    base = datetime.strptime(said_on, "%Y-%m-%d")

    def weekday(m: re.Match[str]) -> str:
        idx = 6 if m.group(1).lower() == "chủ nhật" else _DAY_NAMES[m.group(2).lower()]
        monday = base - timedelta(days=base.weekday())
        if m.group(3).lower() != "này":
            monday += timedelta(days=7)
        day = monday + timedelta(days=idx)
        return f"{m.group(1)} ngày {day:%d/%m/%Y}"

    def simple(m: re.Match[str]) -> str:
        return f"ngày {base + timedelta(days=_SIMPLE_DAYS[m.group(0).lower()]):%d/%m/%Y}"

    def next_week(m: re.Match[str]) -> str:
        monday = base - timedelta(days=base.weekday()) + timedelta(days=7)
        return f"tuần bắt đầu ngày {monday:%d/%m/%Y}"

    text = _WEEKDAY_RE.sub(weekday, text)
    text = _SIMPLE_RE.sub(simple, text)
    return _NEXT_WEEK_RE.sub(next_week, text)


_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _dates(text: str):
    out = []
    for d, m, y in _DATE_RE.findall(text):
        try:
            out.append(datetime(int(y), int(m), int(d)).date())
        except ValueError:  # "31/02/2026" do anh gõ nhầm: bỏ qua thay vì làm hỏng cả lượt chat
            continue
    return out


def event_status(text: str, today: datetime | None) -> str:
    """Gắn nhãn đã diễn ra / hôm nay / sắp tới cho điều có ngày cụ thể. Đo thật: câu "Anh sắp đi phỏng vấn vào ngày
    13/11" khiến model vẫn nói "sắp" vào ngày 14/11; so ngày là việc của code."""
    dates = _dates(text)
    if today is None or not dates:
        return ""
    last = max(dates)
    if last < today.date():
        return " (đã diễn ra)"
    if last == today.date():
        return " (là hôm nay)"
    return " (sắp tới)"


def said_when(said_on: str, today: datetime | None) -> str:
    """"hôm nay" / "hôm qua" / "7 ngày trước": spike cho thấy chỉ có ngày thì model không tự tính được đã bao lâu."""
    day = datetime.strptime(said_on, "%Y-%m-%d")
    if today is None:
        return f"anh nói ngày {day:%d/%m/%Y}"
    ago = (today.date() - day.date()).days
    if ago <= 0:
        return f"anh nói hôm nay, {day:%d/%m/%Y}"
    if ago == 1:
        return f"anh nói hôm qua, {day:%d/%m/%Y}"
    return f"anh nói {ago} ngày trước, ngày {day:%d/%m/%Y}"


def render_memory(facts: list[Fact], limit: int = MEMORY_PROMPT_CHARS, today: datetime | None = None) -> str:
    """Danh sách điều đã nhớ cho system prompt: điều cơ bản trước, rồi điều mới nhất; cắt theo giới hạn ký tự."""
    ordered = [f for f in facts if f.kind in SINGLE_VALUE] + [f for f in reversed(facts) if f.kind not in SINGLE_VALUE]
    lines, used = [], 0
    for f in ordered:
        text = resolve_relative_dates(f.text, f.said_on)
        line = f"- {text}{event_status(text, today)} ({said_when(f.said_on, today)})"
        if used + len(line) > limit:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def system_prompt(now: datetime, facts: list[Fact], episodes: str = "") -> str:
    """episodes: các buổi trò chuyện trước đã tóm tắt (app.episodes.render_episodes), rỗng nếu chưa có."""
    parts = [SYSTEM_PROMPT, "", today_line(now)]
    memory = render_memory(facts, today=now)
    if memory:
        parts += ["", "Những điều em đã biết về anh (từ các lần trò chuyện trước). Chỉ nhắc khi liên quan, đừng kể lể; "
                      "không suy ra hay bịa thêm điều gì ngoài danh sách này:", memory]
    if episodes:
        parts += ["", "Các lần trò chuyện gần đây (tóm tắt, mới nhất trước). Dùng để nối tiếp câu chuyện khi hợp lý; "
                      "không bịa thêm chi tiết:", episodes]
    return "\n".join(parts)


EXTRACT_PROMPT = """Bạn là bộ nhớ của một nhân vật AI tên Mira. Đọc tin nhắn mới nhất của người dùng (anh) và chọn ra
những thông tin ĐÁNG NHỚ LÂU DÀI về anh.

Quy tắc:
- Chỉ lấy điều anh tự nói về bản thân. Không suy đoán, không bịa.
- Bỏ qua chào hỏi, câu hỏi, cảm xúc thoáng qua.
- Mỗi ý là một câu ngắn ở ngôi thứ ba, bắt đầu bằng "Anh", vd "Anh tên là Khoa".
- Gán đúng một loại: {kinds}.
- Giữ nguyên cách anh nói về thời gian ("thứ Bảy tuần sau"), không tự đổi sang ngày.
- Không lặp lại điều đã có trong ĐÃ BIẾT. Không có gì đáng nhớ thì trả về danh sách rỗng.

ĐÃ BIẾT:
{known}

TIN NHẮN MỚI CỦA ANH:
{message}

Trả về JSON đúng dạng: {{"facts": [{{"loai": "...", "noi_dung": "..."}}]}}"""


def extract_messages(message: str, known: list[Fact]) -> list[dict[str, str]]:
    known_text = "\n".join(f"- [{f.kind}] {f.text}" for f in known) or "(chưa có)"
    prompt = EXTRACT_PROMPT.format(kinds=", ".join(KINDS), known=known_text, message=message)
    return [{"role": "user", "content": prompt}]


def parse_facts(raw: str) -> list[tuple[str, str]]:
    """Đọc JSON model trả về; phần hỏng thì bỏ qua (không làm lỗi chat)."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    items = data.get("facts") if isinstance(data, dict) else None
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("noi_dung", "")).split())[:MAX_FACT_CHARS]
        if len(text) < 4:
            continue
        kind = str(item.get("loai", "")).strip().lower()
        out.append((kind if kind in KINDS else "khac", text))
    return out


MIN_MESSAGE_CHARS = 8  # "ok", "hi" không có gì để nhớ, khỏi tốn một lượt gọi model


async def remember(llm, store: MemoryStore, message: str, now: datetime) -> dict:
    """Trích điều đáng nhớ từ tin của người dùng và lưu lại. Trả số liệu cho log."""
    if len(message.strip()) < MIN_MESSAGE_CHARS:
        return {"added": 0, "replaced": 0, "skipped": True}
    raw = await llm.complete(extract_messages(message, store.facts()), json_mode=True)
    return store.add(parse_facts(raw), said_on=now.strftime("%Y-%m-%d"))


def make_memory(root: Path) -> MemoryStore | None:
    if os.getenv("MEMORY_ENABLED", "true").strip().lower() in ("false", "0", "off", "no"):
        return None
    return MemoryStore(root / "data" / "memory.json")
