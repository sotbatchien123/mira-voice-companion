import os

import pytest

# TestClient gửi Host "testserver"; app chỉ nhận tên máy cho phép (chặn DNS rebinding), nên thêm vào trước khi import app
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

from app.main import (app, get_episodes, get_memory, get_presence, get_stt, get_tts, get_turn_log,
                      get_voice_style)
from app.presence import Presence
from app.turn_log import TurnLog
from app.voice_style import VoiceStyle


@pytest.fixture(autouse=True)
def offline_voice_and_log(tmp_path):
    """Mặc định mọi test: không có engine giọng/nghe thật, log lượt chat ghi vào thư mục tạm."""
    app.dependency_overrides[get_tts] = lambda: None
    app.dependency_overrides[get_stt] = lambda: None
    app.dependency_overrides[get_memory] = lambda: None
    app.dependency_overrides[get_episodes] = lambda: None
    style = VoiceStyle()  # thời gian chờ tiếng cười không lây giữa các test
    app.dependency_overrides[get_voice_style] = lambda: style
    presence = Presence(tmp_path / "presence.json")  # không đụng data/ thật
    app.dependency_overrides[get_presence] = lambda: presence
    app.dependency_overrides[get_turn_log] = lambda: TurnLog(tmp_path / "turns.jsonl")
    yield tmp_path / "turns.jsonl"
    app.dependency_overrides.clear()
