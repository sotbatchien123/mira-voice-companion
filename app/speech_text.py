"""Chuẩn bị chữ cho TTS: tách câu trả lời đang stream thành đoạn để đọc sớm, và lọc ký tự không đọc được."""

from __future__ import annotations

import re
import unicodedata

SENTENCE_END = ".!?…\n"
SOFT_BREAK = ",;:"
CLOSING = "\"')]»”’"


def _letters(s: str) -> int:
    return sum(c.isalpha() for c in s)


class SpeechSegmenter:
    """Gom chữ stream thành đoạn để đọc.

    Đoạn đầu được cắt sớm ở dấu phẩy nếu đã đủ dài (giống faster_first_response của Open-LLM-VTuber),
    các đoạn sau cắt ở dấu kết thúc câu. Đoạn quá ngắn ("Ô!") được gộp vào đoạn sau.
    """

    def __init__(self, first_min_chars: int = 12, min_letters: int = 4) -> None:
        self.first_min_chars = first_min_chars
        self.min_letters = min_letters
        self._buf = ""
        self._first = True

    def push(self, text: str) -> list[str]:
        self._buf += text
        out = []
        while (seg := self._take()) is not None:
            out.append(seg)
        return out

    def flush(self) -> list[str]:
        rest, self._buf = self._buf.strip(), ""
        return [rest] if _letters(rest) else []

    def _take(self) -> str | None:
        buf = self._buf
        i = 0
        while i < len(buf):
            soft = self._first and buf[i] in SOFT_BREAK
            if buf[i] not in SENTENCE_END and not soft:
                i += 1
                continue
            j = i + 1
            while j < len(buf) and buf[j] in SENTENCE_END + SOFT_BREAK + CLOSING:
                j += 1
            if j == len(buf) and buf[j - 1] != "\n":
                return None  # chưa biết ký tự kế tiếp (vd "3." có thể là "3.5")
            if buf[j - 1] != "\n" and not buf[j].isspace():
                i = j
                continue
            seg = buf[:j].strip()
            if _letters(seg) >= self.min_letters and (not soft or len(seg) >= self.first_min_chars):
                self._buf = buf[j:]
                self._first = False
                return seg
            i = j
        return None


_KEEP_PUNCT = set(".,!?;:…'\"-()%/")
_DROP = {"‍", "️", "︎"}  # nối emoji, chọn kiểu emoji


def clean_for_speech(text: str) -> str:
    """Bỏ emoji, ký hiệu markdown và ký tự lạ; giữ chữ (kể cả dấu tiếng Việt), số và dấu câu cơ bản."""
    out = []
    for ch in unicodedata.normalize("NFC", text):
        if ch in _DROP:
            continue
        cat = unicodedata.category(ch)
        if cat[0] in "LNM" or ch in _KEEP_PUNCT:
            out.append(ch)
        else:
            out.append(" ")
    cleaned = re.sub(r"\s+", " ", "".join(out))
    cleaned = re.sub(r"\s+([.,!?;:…])", r"\1", cleaned).strip()  # "buồn ." (sau khi bỏ emoji) -> "buồn."
    return cleaned if _letters(cleaned) else ""
