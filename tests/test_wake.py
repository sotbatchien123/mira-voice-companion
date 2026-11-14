"""Test từ đánh thức (spec 007). Câu lấy từ đo thật: VieNeu đọc -> Zipformer nghe (3 giọng)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_stt
from app.wake import detect_wake, wake_settings

# Zipformer nghe các câu gọi tên thế này (kể cả nghe nhầm tên)
HEARD_CALLS = [
    ("Mira ơi hôm nay trời đẹp quá", "Mira ơi hôm nay trời đẹp quá"),
    ("Vera ơi hôm nay trời đẹp quá", "Mira ơi hôm nay trời đẹp quá"),
    ("Me ra ơi hôm nay trời đẹp quá", "Mira ơi hôm nay trời đẹp quá"),
    ("Mira à em đang làm gì đó", "Mira à em đang làm gì đó"),
    ("Vira à em đang làm gì đó", "Mira à em đang làm gì đó"),
    ("Mira a em đang làm gì đó", "Mira a em đang làm gì đó"),
    ("Này mới ra kể chuyện vui đi", "Này Mira kể chuyện vui đi"),
    ("Này mi ra kể chuyện vui đi", "Này Mira kể chuyện vui đi"),
    ("Này mira kể chuyện vui đi", "Này Mira kể chuyện vui đi"),
    ("Mira ơi", "Mira ơi"),
    ("Visa ơi", "Mira ơi"),
    ("Mara ơi", "Mira ơi"),
    ("Emmira anh về rồi nè", "Ê Mira anh về rồi nè"),
    ("Misa ơi em có đó không", "Mira ơi em có đó không"),
    ("Đi ra ơi em có đó không", "Mira ơi em có đó không"),
    ("Chào Mira, anh về rồi", "Chào Mira, anh về rồi"),
]

NOT_CALLS = [
    "Hôm nay trời đẹp quá",
    "Bật tivi lên bi con",
    "Tập tv lên đi con",
    "Mai mình đi chợ nhà",
    "Hôm nay mình đi chợ nhé",
    "Chị mai ơi ăn cơm chưa",
    "Mía ở chợ rẻ lắm",
    "Tía ở chợ rẻ lắm",
    "Nhớ ở chợ rẻ lắm",
    "Đi ra ngoài chơi đi",
    "Đi ra à",
    "Này đi ra ngoài đi",
    "Visa của anh hết hạn rồi",
    "Camera nhà mình hỏng rồi",
    "Anh vừa nói chuyện với Mira",  # tên ở giữa câu: không phải gọi
    "",
]


@pytest.mark.parametrize(("heard", "fixed"), HEARD_CALLS)
def test_nhan_ra_tieng_goi_va_sua_ten(heard, fixed):
    assert detect_wake(heard) == (True, fixed)


@pytest.mark.parametrize("heard", NOT_CALLS)
def test_khong_nhan_nham(heard):
    assert detect_wake(heard) == (False, heard)


def test_ty_le_nhan_ra_cau_do_duoc():
    # Đo thật 15 câu gọi tên: chỉ "Camera anh về rồi nè" (Ê Mira) là chịu, vì "camera" đầu câu là từ thường
    measured = [h for h, _ in HEARD_CALLS[:15]] + ["Camera anh về rồi nè"]
    hits = sum(detect_wake(t)[0] for t in measured)
    assert hits / len(measured) >= 0.9


def test_cau_hinh(monkeypatch):
    assert wake_settings() == {"required": True, "window_seconds": 60}
    monkeypatch.setenv("HANDSFREE_WAKE_WORD", "false")
    monkeypatch.setenv("WAKE_WINDOW_SECONDS", "abc")
    assert wake_settings() == {"required": False, "window_seconds": 60}


class FakeSTT:
    name = "fake"

    def __init__(self, text):
        self.text = text

    def transcribe(self, pcm):
        return self.text


@pytest.mark.parametrize(("heard", "wake", "text"), [
    ("Vera ơi kể chuyện đi", True, "Mira ơi kể chuyện đi"),
    ("Bật tivi lên đi con", False, "Bật tivi lên đi con"),
])
def test_api_stt_tra_wake(heard, wake, text):
    app.dependency_overrides[get_stt] = lambda: FakeSTT(heard)
    try:
        res = TestClient(app).post("/api/stt", content=b"\0" * 16000)
    finally:
        app.dependency_overrides.pop(get_stt)
    assert res.status_code == 200
    assert res.json()["wake"] is wake
    assert res.json()["text"] == text


def test_health_co_wake():
    body = TestClient(app).get("/api/health").json()
    assert body["wake"] == {"required": True, "window_seconds": 60}
