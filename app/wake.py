"""Từ đánh thức "Mira ơi" cho chế độ Rảnh tay (spec 007).

STT hay nghe nhầm cái tên lạ "Mira" ("Vera ơi", "Misa ơi", "Này mới ra", "Camera"...), nên nhận diện mờ: chỉ xét
1–2 từ đầu câu, so trên chữ đã bỏ dấu. Tên chắc chắn thì nhận luôn; tên dễ nhầm với từ thường thì phải có tiếng gọi
("ơi/à/a") phía sau hoặc "này/ê/chào" phía trước.
"""

from __future__ import annotations

import os
import re
import unicodedata

NAME = "Mira"

# Bỏ dấu rồi so: "mi ra" = ("mi", "ra")
STRONG = {("mira",), ("myra",), ("meera",), ("emmira",), ("emira",)}
WEAK = {("vera",), ("vira",), ("mara",), ("misa",), ("visa",), ("mila",), ("camera",),
        ("mi", "ra"), ("me", "ra"), ("moi", "ra"), ("di", "ra")}
CALLS = {"oi", "a", "o", "ui"}  # ơi, à, a, ạ, ơ
STRICT_CALLS = {("di", "ra"): {"oi"}}  # "đi ra à?" là câu hỏi thường, chỉ "đi ra ơi" mới tính
PREFIXES = {"nay", "e", "chao", "alo", "hey"}  # này, ê, chào

_WORD = re.compile(r"\w+")


def fold(word: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt: "Mới" -> "moi", "Đi" -> "di"."""
    word = word.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c))


def detect_wake(text: str) -> tuple[bool, str]:
    """Câu có mở đầu bằng tiếng gọi Mira không. Trả (có_gọi, câu với tên viết lại đúng "Mira")."""
    words = list(_WORD.finditer(text))
    folded = [fold(m.group()) for m in words]
    starts = [0, 1] if folded and folded[0] in PREFIXES else [0]
    for start in starts:
        for size in (2, 1):
            name = tuple(folded[start:start + size])
            if len(name) < size or (name not in STRONG and name not in WEAK):
                continue
            nxt = folded[start + size] if start + size < len(folded) else None
            called = nxt in STRICT_CALLS.get(name, CALLS)
            if name in WEAK and not called and start == 0:
                continue
            if name in STRICT_CALLS and not called:
                continue
            first, last = words[start], words[start + size - 1]
            # "Emmira"/"Camera" là "Ê Mira" bị dính: giữ tiếng gọi, chỉ sửa tên
            fixed = f"Ê {NAME}" if name in {("emmira",), ("emira",), ("camera",)} else NAME
            return True, text[: first.start()] + fixed + text[last.end():]
    return False, text


def wake_settings() -> dict:
    """Cấu hình cho trình duyệt: có đòi tên khi rảnh tay không, và cửa sổ trò chuyện bao lâu."""
    required = os.getenv("HANDSFREE_WAKE_WORD", "true").strip().lower() not in ("false", "0", "off", "no")
    try:
        window = max(0, int(os.getenv("WAKE_WINDOW_SECONDS", "60")))
    except ValueError:
        window = 60
    return {"required": required, "window_seconds": window}
