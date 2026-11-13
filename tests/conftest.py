import pytest

from app.main import app, get_tts, get_turn_log
from app.turn_log import TurnLog


@pytest.fixture(autouse=True)
def offline_voice_and_log(tmp_path):
    """Mặc định mọi test: không có engine giọng thật, log lượt chat ghi vào thư mục tạm."""
    app.dependency_overrides[get_tts] = lambda: None
    app.dependency_overrides[get_turn_log] = lambda: TurnLog(tmp_path / "turns.jsonl")
    yield tmp_path / "turns.jsonl"
    app.dependency_overrides.clear()
