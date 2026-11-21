"""Mira chủ động: nhớ lúc người dùng nói lần cuối và lúc chào lần cuối (data/presence.json), quyết định có nên chào
/ hỏi thăm không, và dựng lời nhắc cho model (không hiện ra, không lưu lịch sử)."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("waifu")


def _minutes(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


class Presence:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.greeting = os.getenv("PROACTIVE_GREETING", "true").strip().lower() not in ("false", "0", "off", "no")
        self.greet_min_gap = timedelta(minutes=_minutes("GREET_MIN_GAP_MINUTES", 30))
        self.checkin_minutes = _minutes("PROACTIVE_CHECKIN_MINUTES", 10)  # 0 = tắt
        self.last_user_at: datetime | None = None
        self.last_greet_at: datetime | None = None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.last_user_at = _parse(raw.get("last_user_at"))
            self.last_greet_at = _parse(raw.get("last_greet_at"))
        except FileNotFoundError:
            pass
        except (ValueError, AttributeError):
            path.replace(path.with_suffix(path.suffix + ".bad"))  # để còn cứu tay, đừng để lần ghi sau đè mất
            log.warning("file %s hỏng, cất bản hỏng ra .bad rồi bắt đầu lại", path)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"last_user_at": _iso(self.last_user_at), "last_greet_at": _iso(self.last_greet_at)}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self.path)

    def user_spoke(self, now: datetime) -> None:
        with self._lock:
            self.last_user_at = now
            self._save()

    def should_greet(self, now: datetime) -> bool:
        if not self.greeting:
            return False
        recent = [t for t in (self.last_user_at, self.last_greet_at) if t is not None]
        return not recent or now - max(recent) >= self.greet_min_gap

    def should_check_in(self, now: datetime) -> bool:
        if not self.checkin_minutes or self.last_user_at is None:
            return False
        return now - self.last_user_at >= timedelta(minutes=self.checkin_minutes)

    def greeted(self, now: datetime) -> None:
        with self._lock:
            self.last_greet_at = now
            self._save()


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def describe_gap(last: datetime | None, now: datetime) -> str:
    """Khoảng vắng bằng lời, để model chào cho hợp ("khoảng 3 tiếng", "khoảng 2 ngày")."""
    if last is None:
        return "chưa từng nói chuyện, đây là lần đầu gặp"
    minutes = (now - last).total_seconds() / 60
    if minutes < 60:
        return f"khoảng {max(1, round(minutes))} phút trước"
    if minutes < 24 * 60:
        return f"khoảng {round(minutes / 60)} tiếng trước"
    days = round(minutes / (24 * 60))
    return "khoảng 1 ngày trước" if days == 1 else f"khoảng {days} ngày trước"


NOTE = "(Ghi chú hệ thống, anh không nhìn thấy dòng này)"
RULES = "Không nhắc tới ghi chú này, không nhắc tới ứng dụng/app/màn hình, không bịa chuyện anh chưa kể."


def proactive_prompt(kind: str, last_user_at: datetime | None, now: datetime) -> str:
    gap = describe_gap(last_user_at, now)
    if kind == "greet":
        return (f"{NOTE} Anh vừa quay lại. Lần trò chuyện trước: {gap}. Hãy chủ động chào anh một câu ngắn (1-2 câu), "
                "hợp với buổi hiện tại. Nếu trong những điều đã biết có chuyện đáng hỏi thăm (sự kiện vừa qua hoặc sắp tới, "
                f"thú cưng...) thì hỏi thăm MỘT chuyện thôi; không có thì chào bình thường. {RULES}")
    return (f"{NOTE} Anh im lặng đã {gap.removesuffix(' trước')}. Hai người đang giữa cuộc trò chuyện nên KHÔNG chào lại. "
            "Hãy hỏi thăm nhẹ nhàng một câu ngắn để bắt chuyện lại, không trách móc, không hỏi dồn; chỉ nhắc điều có trong "
            f"cuộc trò chuyện hoặc trong những điều đã biết. {RULES}")
