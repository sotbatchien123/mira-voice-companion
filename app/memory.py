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
from datetime import datetime
from pathlib import Path

from .persona import SYSTEM_PROMPT

log = logging.getLogger("waifu")

KINDS = ("ten", "tuoi", "nghe_nghiep", "noi_o", "cach_goi", "gia_dinh", "thu_cung", "so_thich", "khong_thich",
         "suc_khoe", "su_kien", "khac")
SINGLE_VALUE = {"ten", "tuoi", "nghe_nghiep", "noi_o", "cach_goi"}  # điều mới thay điều cũ cùng loại
MAX_FACTS = 60
MAX_FACT_CHARS = 200
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


def today_line(now: datetime) -> str:
    return f"Bây giờ là {now:%H:%M}, {WEEKDAYS[now.weekday()]} ngày {now:%d/%m/%Y}."


def render_memory(facts: list[Fact], limit: int = MEMORY_PROMPT_CHARS) -> str:
    """Danh sách điều đã nhớ cho system prompt: điều cơ bản trước, rồi điều mới nhất; cắt theo giới hạn ký tự."""
    ordered = [f for f in facts if f.kind in SINGLE_VALUE] + [f for f in reversed(facts) if f.kind not in SINGLE_VALUE]
    lines, used = [], 0
    for f in ordered:
        day = datetime.strptime(f.said_on, "%Y-%m-%d").strftime("%d/%m/%Y")
        line = f"- {f.text} (anh nói ngày {day})"
        if used + len(line) > limit:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def system_prompt(now: datetime, facts: list[Fact]) -> str:
    parts = [SYSTEM_PROMPT, "", today_line(now)]
    memory = render_memory(facts)
    if memory:
        parts += ["", "Những điều em đã biết về anh (từ các lần trò chuyện trước). Chỉ nhắc khi liên quan, đừng kể lể; "
                      "không suy ra hay bịa thêm điều gì ngoài danh sách này:", memory]
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
