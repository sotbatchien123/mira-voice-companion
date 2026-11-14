"""Tách tag cảm xúc kiểu "[happy]" ra khỏi luồng text đang stream từ LLM.

Text sạch gửi cho frontend (sau này đưa thẳng vào TTS), còn cảm xúc dùng để đổi biểu cảm avatar.
Làm ở server để mọi thứ phía sau (giao diện, TTS) chỉ nhận text đã sạch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tên expression chuẩn của VRM 1.0 (three-vrm tự map cho model VRM 0.x)
EMOTIONS = ("neutral", "happy", "angry", "sad", "relaxed", "surprised")

ALIASES: dict[str, str] = {
    **{e: e for e in EMOTIONS},
    "smile": "happy",
    "laugh": "happy",
    "blush": "happy",
    "shy": "happy",
    "pout": "angry",
    "annoyed": "angry",
    "cry": "sad",
    "calm": "relaxed",
    "shock": "surprised",
    # Model local hay tự chế thêm tag (đã gặp [concerned] khi chạy thật)
    "excited": "happy",
    "playful": "happy",
    "cheerful": "happy",
    "embarrassed": "happy",
    "concerned": "sad",
    "worried": "sad",
    "sigh": "sad",
    "upset": "sad",
    "mad": "angry",
    "curious": "surprised",
    "confused": "surprised",
    "gentle": "relaxed",
    "soft": "relaxed",
    "thinking": "neutral",
}

# Tag dài hơn mức này thì coi như text thường, không giữ lại chờ dấu "]" nữa
MAX_TAG_LEN = 16
# Nuốt luôn dấu cách sau tag, để "sao? [sad] Nhớ" thành "sao? Nhớ" chứ không còn 2 dấu cách
TAG_RE = re.compile(r"\[([A-Za-z_]{1,16})\][ \t]*")
SPACES = " \t"


@dataclass
class ParsedChunk:
    text: str = ""
    emotions: list[str] = field(default_factory=list)
    ends_with_tag: bool = False  # chuỗi kết thúc ngay sau một tag đã bỏ
    marks: list[tuple[int, str]] = field(default_factory=list)  # (vị trí trong text, cảm xúc) của từng tag


def parse_complete(source: str) -> ParsedChunk:
    """Parse một chuỗi đã hoàn chỉnh (không còn tag dở dang).

    Tag lạ (model tự chế, vd [shrug]) bị bỏ đi mà không đổi cảm xúc: để lại thì hiện trong khung chat và bị
    TTS đọc thành tiếng.
    """
    emotions: list[str] = []
    ends_with_tag = False
    marks: list[tuple[int, str]] = []
    parts: list[str] = []
    pos = 0
    for match in TAG_RE.finditer(source):
        parts.append(source[pos:match.start()])
        pos = match.end()
        emotion = ALIASES.get(match.group(1).lower())
        if emotion is not None:
            marks.append((sum(map(len, parts)), emotion))
            emotions.append(emotion)
        ends_with_tag = match.end() == len(source)
    parts.append(source[pos:])
    return ParsedChunk("".join(parts), emotions, ends_with_tag, marks)


class EmotionTagParser:
    """Parser có trạng thái cho text stream: tag có thể bị cắt giữa hai chunk, vd "[hap" + "py]"."""

    def __init__(self) -> None:
        self._pending = ""
        self._eat_space = False  # tag vừa bỏ nằm cuối mảnh trước -> bỏ dấu cách đầu mảnh này

    def push(self, chunk: str) -> ParsedChunk:
        self._pending += chunk

        hold = ""
        open_idx = self._pending.rfind("[")
        if open_idx != -1 and "]" not in self._pending[open_idx:]:
            tail = self._pending[open_idx:]
            if len(tail) <= MAX_TAG_LEN + 1:
                hold = tail
                self._pending = self._pending[:open_idx]

        result = self._parse(self._pending)
        self._pending = hold
        return result

    def flush(self) -> ParsedChunk:
        """Gọi khi stream kết thúc để xả phần còn giữ lại."""
        result = self._parse(self._pending)
        self._pending = ""
        return result

    def _parse(self, source: str) -> ParsedChunk:
        if self._eat_space:
            source = source.lstrip(SPACES)
        result = parse_complete(source)
        if source:
            self._eat_space = result.ends_with_tag
        return result
