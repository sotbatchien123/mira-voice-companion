import pytest

from app.main import app, get_memory, get_presence, get_stt, get_tts, get_turn_log
from app.presence import Presence
from app.turn_log import TurnLog


@pytest.fixture(autouse=True)
def offline_voice_and_log(tmp_path):
    """Mặc định mọi test: không có engine giọng/nghe thật, log lượt chat ghi vào thư mục tạm."""
    app.dependency_overrides[get_tts] = lambda: None
    app.dependency_overrides[get_stt] = lambda: None
    app.dependency_overrides[get_memory] = lambda: None
    presence = Presence(tmp_path / "presence.json")  # không đụng data/ thật
    app.dependency_overrides[get_presence] = lambda: presence
    app.dependency_overrides[get_turn_log] = lambda: TurnLog(tmp_path / "turns.jsonl")
    yield tmp_path / "turns.jsonl"
    app.dependency_overrides.clear()
