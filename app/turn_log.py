"""Ghi một dòng JSON cho mỗi lượt chat: độ trễ từng khâu, model, engine giọng, lỗi.

Không ghi nội dung tin nhắn. Dùng để so sánh khi đổi model hoặc engine.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("waifu")


class TurnLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, record: dict) -> None:
        line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            log.warning("không ghi được log lượt chat vào %s", self.path, exc_info=True)  # log hỏng không được làm hỏng chat
