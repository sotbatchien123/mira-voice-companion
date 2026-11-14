"""Test giọng theo cảm xúc (spec 008): tín hiệu [cười]/[thở dài] có thời gian chờ, tốc độ phát theo cảm xúc."""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_llm, get_tts, get_voice_style
from app.voice_style import VoiceStyle
from tests.test_voice import FakeLLM, FakeTTS, events


class CueTTS(FakeTTS):
    supports_cues = True


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def chat(chunks, tts, style):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(chunks)
    app.dependency_overrides[get_tts] = lambda: tts
    app.dependency_overrides[get_voice_style] = lambda: style
    try:
        res = TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": "Chào em"}], "voice": True})
    finally:
        app.dependency_overrides.pop(get_voice_style)
    return events(res.text)


def test_cuoi_mot_lan_trong_thoi_gian_cho():
    clock = Clock()
    style = VoiceStyle(clock)
    assert style.cue("happy") == "[cười]"
    assert style.cue("happy") is None  # vừa cười xong
    assert style.cue("sad") == "[thở dài]"  # mỗi loại đếm riêng
    assert style.cue("neutral") is None
    assert style.cue(None) is None
    clock.now += style.cooldown_s
    assert style.cue("happy") == "[cười]"


def test_tat_bang_cau_hinh(monkeypatch):
    monkeypatch.setenv("VOICE_EMOTION_CUES", "false")
    monkeypatch.setenv("VOICE_EMOTION_SPEED", "off")
    style = VoiceStyle()
    assert style.cue("happy") is None
    assert style.speed_for("happy") == 1.0


def test_toc_do_theo_cam_xuc():
    style = VoiceStyle()
    assert style.speed_for("happy") > 1.0
    assert style.speed_for("sad") < 1.0
    assert style.speed_for("neutral") == style.speed_for(None) == 1.0


REPLY = "[happy] Thật hả anh? Em vui quá đi mất! Hay quá. [sad] Nhưng mà tiếc ghê."


@pytest.mark.parametrize("chunks", [
    [REPLY],  # cả câu trong một mảnh, có 2 tag
    re.findall(r"\S+\s*", REPLY),  # từng từ như model stream thật
    list(REPLY),  # từng ký tự: tag bị cắt đôi giữa các mảnh
])
def test_api_chen_tin_hieu_mot_lan_va_gui_toc_do(chunks):
    tts = CueTTS()
    evs = chat(chunks, tts, VoiceStyle(Clock()))
    # Chữ hiện ra và chữ gửi kèm audio không có tín hiệu; chỉ TTS nhận
    assert tts.spoken == ["[cười] Thật hả anh?", "Em vui quá đi mất!", "Hay quá.", "[thở dài] Nhưng mà tiếc ghê."]
    heads = [e for e in evs if e["type"] == "audio" and e["part"] == 0]
    assert [h["text"] for h in heads] == ["Thật hả anh?", "Em vui quá đi mất!", "Hay quá.", "Nhưng mà tiếc ghê."]
    assert [h.get("speed") for h in heads] == [1.05, 1.05, 1.05, 0.94]
    assert all("speed" not in e for e in evs if e["type"] == "audio" and e["part"] > 0)
    shown = "".join(e["text"] for e in evs if e["type"] == "text")
    assert "[" not in shown


def test_engine_khong_hieu_tin_hieu_thi_khong_chen():
    tts = FakeTTS()  # như Piper: sẽ đọc to nguyên chữ "[cười]"
    chat(["[happy] Thật hả anh? Em vui quá đi mất!"], tts, VoiceStyle(Clock()))
    assert tts.spoken == ["Thật hả anh?", "Em vui quá đi mất!"]


def test_cau_trung_tinh_khong_gui_toc_do():
    evs = chat(["Hôm nay anh ăn trưa chưa?"], CueTTS(), VoiceStyle(Clock()))
    heads = [e for e in evs if e["type"] == "audio" and e["part"] == 0]
    assert heads and all("speed" not in h for h in heads)
