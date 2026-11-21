"""Giọng theo cảm xúc (spec 008).

Hai núm, đều bật/tắt được trong .env:
- Tín hiệu phi ngôn ngữ của VieNeu: "[cười]" trước câu vui, "[thở dài]" trước câu buồn. Đo: thêm ~0,9s / ~0,5s tiếng
  thật, STT không đọc thành chữ. Cười mỗi câu thì lố, nên mỗi loại chỉ một lần trong COOLDOWN giây.
- Tốc độ phát (kèm cao độ, như playbackRate của trình duyệt): vui nhanh/cao hơn chút, buồn chậm/trầm hơn chút. Làm ở
  trình duyệt nên không tốn CPU; server chỉ gửi kèm hệ số `speed` ở mảnh đầu mỗi đoạn.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from .util import env_flag, env_number

CUES = {"happy": "[cười]", "sad": "[thở dài]"}
SPEEDS = {"happy": 1.05, "surprised": 1.05, "sad": 0.94}


class VoiceStyle:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.cues = env_flag("VOICE_EMOTION_CUES")
        self.speed = env_flag("VOICE_EMOTION_SPEED")
        self.cooldown_s = env_number("VOICE_CUE_COOLDOWN_SECONDS", 120.0)
        self._clock = clock
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def cue(self, emotion: str | None) -> str | None:
        """Tín hiệu chèn trước đoạn này, hoặc None. Gọi là tính đã dùng (bắt đầu đếm lại thời gian chờ)."""
        if not self.cues or emotion not in CUES:
            return None
        with self._lock:
            now = self._clock()
            last = self._last.get(emotion)
            if last is not None and now - last < self.cooldown_s:
                return None
            self._last[emotion] = now
            return CUES[emotion]

    def speed_for(self, emotion: str | None) -> float:
        return SPEEDS.get(emotion or "", 1.0) if self.speed else 1.0
