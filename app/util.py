"""Hai việc nhỏ mà nhiều module cùng cần: ghi file JSON an toàn và đọc cấu hình từ biến môi trường."""

from __future__ import annotations

import json
import os
from pathlib import Path


def write_json(path: Path, data: dict, indent: int | None = 1) -> None:
    """Ghi nguyên tử: ghi ra file tạm rồi đổi tên, tắt máy giữa chừng không làm hỏng file cũ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    tmp.replace(path)


def env_flag(name: str, default: bool = True) -> bool:
    return os.getenv(name, "true" if default else "false").strip().lower() not in ("false", "0", "off", "no")


def env_number(name: str, default: int | float) -> int | float:
    """Số không âm, cùng kiểu với default; viết sai thì dùng default."""
    try:
        return max(0, type(default)(os.getenv(name, str(default))))
    except ValueError:
        return default
