"""Tách câu tiếng Nhật trong thẻ <ja>…</ja> ra khỏi luồng text đang stream từ LLM.

Phần hiển thị (tiếng Việt) đi tiếp như cũ, còn câu tiếng Nhật được gom riêng để đưa vào TTS tiếng Nhật.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

OPEN_RE = re.compile(r"<(?:ja|jp)>", re.IGNORECASE)
CLOSE_RE = re.compile(r"</(?:ja|jp)>", re.IGNORECASE)
# Đuôi "<…" ngắn hơn mức này (dài nhất là "</ja>") có thể còn thành thẻ -> giữ lại chờ chunk sau
MAX_TAG_LEN = 5
# Kana, kanji, dấu câu và ký tự full-width
JA_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uff01-\uff5e\u3000-\u303f]+")
# Cặp ngoặc bị trống sau khi bỏ chữ Nhật, vd "(おかえり)" -> "()"
EMPTY_BRACKETS_RE = re.compile(r"\(\s*\)|（\s*）|「\s*」")
SPACES_RE = re.compile(r" {2,}")
# Thẻ ja/jp lạc chỗ (vd "</ja>" không có thẻ mở) không được lộ ra màn hình
STRAY_TAG_RE = re.compile(r"</?(?:ja|jp)>", re.IGNORECASE)
# Thẻ dở dang cuối luồng, vd "<ja" hoặc "</"
PARTIAL_TAG_RE = re.compile(r"</?(?:j|ja|jp)?$", re.IGNORECASE)
# Đuôi cần giữ lại: dấu cách và/hoặc "(" có thể sắp thành "()" hoặc dấu cách đôi ở mảnh sau
TAIL_RE = re.compile(r" *(?:\( *)?$")
# Câu đọc phải có kana/kanji; không có (model quên dịch) thì bỏ, không để giọng Nhật đọc chữ Việt
SPEAKABLE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
EMOTION_TAG_RE = re.compile(r"\[[a-z_]+\]")
# Model quên </ja>: chữ Việt/Latin bắt đầu sau dấu hết câu tiếng Nhật thì trả về màn hình
SPILL_RE = re.compile(r"(?<=[。！？!?])\s*(?=[A-Za-zÀ-ỹĐđ]{2,})")


@dataclass
class JaChunk:
    display: str = ""  # text tiếng Việt để hiển thị
    ja: list[str] = field(default_factory=list)  # các câu tiếng Nhật đã đóng thẻ trong chunk này
    ja_at: list[int] = field(default_factory=list)  # vị trí trong display nơi từng câu ja kết thúc (song song với ja)


class JaTagParser:
    """Parser có trạng thái: thẻ có thể bị cắt giữa hai chunk, vd "<j" + "a>"."""

    def __init__(self) -> None:
        self._pending = ""
        self._in_ja = False
        self._ja_buf = ""
        self._tail = ""  # đuôi (dấu cách, "(") của mảnh trước, chỉ phát ra khi biết chữ theo sau

    def push(self, chunk: str) -> JaChunk:
        self._pending += chunk
        out = JaChunk()
        while True:
            m = (STRAY_TAG_RE if self._in_ja else OPEN_RE).search(self._pending)
            if m is None:
                break
            self._take(self._pending[:m.start()], out)
            if self._in_ja:
                self._end_ja(out)
            # Đang trong thẻ mà gặp <ja> mới: coi như thẻ cũ đã đóng, vẫn ở trong thẻ
            self._in_ja = not self._in_ja or not m.group().startswith("</")
            self._pending = self._pending[m.end():]

        idx = self._pending.rfind("<")
        if idx != -1 and ">" not in self._pending[idx:] and len(self._pending) - idx <= MAX_TAG_LEN:
            body, self._pending = self._pending[:idx], self._pending[idx:]
        else:
            body, self._pending = self._pending, ""
        self._take(body, out)
        return out

    def flush(self) -> JaChunk:
        """Gọi khi stream kết thúc: xả phần giữ lại; thẻ <ja> chưa đóng vẫn được đọc."""
        out = JaChunk()
        self._take(PARTIAL_TAG_RE.sub("", self._pending), out)
        if self._in_ja:
            self._end_ja(out)
        else:
            out.display += self._tail.rstrip(" ")
        self._pending = ""
        self._in_ja = False
        self._tail = ""
        return out

    def _take(self, text: str, out: JaChunk) -> None:
        if self._in_ja:
            self._ja_buf += text
        else:
            out.display += self._clean(text)

    def _end_ja(self, out: JaChunk) -> None:
        ja, *spill = SPILL_RE.split(self._ja_buf, maxsplit=1)
        if spill and SPEAKABLE_RE.search(spill[0]):  # "はい。OKです" vẫn là câu Nhật, không phải chữ Việt sót
            ja, spill = self._ja_buf, []
        ja = EMOTION_TAG_RE.sub("", ja).strip()
        if SPEAKABLE_RE.search(ja):
            out.ja.append(ja)
            out.ja_at.append(len(out.display))
        self._ja_buf = ""
        if spill:
            out.display += self._clean(" " + spill[0])

    def _clean(self, text: str) -> str:
        text = EMPTY_BRACKETS_RE.sub("", STRAY_TAG_RE.sub("", JA_RE.sub("", self._tail + text)))
        text = SPACES_RE.sub(" ", text)
        m = TAIL_RE.search(text)
        self._tail = m.group()
        return text[:m.start()]


def strip_ja(text: str) -> str:
    """Bỏ mọi phần tiếng Nhật khỏi một đoạn text hoàn chỉnh."""
    parser = JaTagParser()
    return parser.push(text).display + parser.flush().display
