"""Ghi một dòng JSON cho mỗi lượt chat: độ trễ từng khâu, model, engine giọng, lỗi.

Không ghi nội dung tin nhắn. Dùng để so sánh khi đổi model hoặc engine.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("waifu")


MAX_LOG_BYTES = 5_000_000  # ~25 nghìn lượt; quá thì đổi sang turns.1.jsonl (chỉ giữ một file cũ)


class TurnLog:
    def __init__(self, path: Path, max_bytes: int = MAX_LOG_BYTES) -> None:
        self.path = path
        self.max_bytes = max_bytes

    def write(self, record: dict) -> None:
        line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                self.path.replace(self.path.with_name(f"{self.path.stem}.1{self.path.suffix}"))
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            log.warning("không ghi được log lượt chat vào %s", self.path, exc_info=True)  # log hỏng không được làm hỏng chat
