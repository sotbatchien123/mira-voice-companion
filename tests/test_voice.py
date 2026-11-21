"""Test phần giọng nói (spec 002) bằng engine giả: không cần file giọng, Piper hay Ollama."""

import base64
import json
import struct
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app, fade_in, get_llm, get_tts
from app.speech_text import SpeechSegmenter, clean_for_speech
from app.tts import PiperTTS, TTSError, VieNeuTTS, make_tts

CHUNK = struct.pack("<4h", 1000, 1000, 1000, 1000)  # 4 mẫu PCM 16-bit


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self, chunks, done=None):
        self.chunks = chunks
        self.done = done  # threading.Event báo đã phát hết chữ

    async def stream(self, history, system=None):
        for c in self.chunks:
            yield ("text", c)
        if self.done:
            self.done.set()
        yield ("stop", "end_turn")

    async def check(self):
        return None


class FakeTTS:
    name = "fake-tts"
    sample_rate = 1000
    segment_pause_s = 0.0

    def __init__(self, fail=False, wait_for=None, pause=0.0):
        self.fail = fail
        self.wait_for = wait_for
        self.segment_pause_s = pause
        self.spoken = []

    def stream(self, text):
        if self.wait_for is not None and not self.wait_for.wait(timeout=3):
            raise TTSError("phải chờ LLM xong mà LLM lại đang chờ giọng")
        if self.fail:
            raise TTSError("giọng hỏng")
        self.spoken.append(text)
        yield CHUNK
        yield CHUNK

    def check(self):
        return None

    def warm_up(self):
        pass


def events(body):
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def chat(chunks, tts, voice=True, done=None):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(chunks, done)
    app.dependency_overrides[get_tts] = lambda: tts
    res = TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": "Chào em"}], "voice": voice})
    return events(res.text)


def segment(chunks):
    s = SpeechSegmenter()
    out = [seg for c in chunks for seg in s.push(c)]
    return out + s.flush()


# ---------- tách đoạn ----------

def test_doan_dau_cat_som_o_dau_phay_khi_du_dai():
    text = "Chào anh, em đang nghe nhạc, rồi xem phim. Anh làm gì đó?"
    assert segment([text]) == ["Chào anh, em đang nghe nhạc,", "rồi xem phim.", "Anh làm gì đó?"]


def test_stream_tung_ky_tu_cho_cung_ket_qua():
    text = "Chào anh, em đang nghe nhạc, rồi xem phim. Anh làm gì đó?"
    assert segment(list(text)) == segment([text])


def test_gop_doan_qua_ngan_va_doc_phan_con_lai_khi_ket_thuc():
    assert segment(["Ô! Anh trúng xổ số à? Vậy"]) == ["Ô! Anh trúng xổ số à?", "Vậy"]


def test_khong_cat_o_dau_cham_thap_phan():
    assert segment(["Giá 3.5 triệu đó anh. Ok"]) == ["Giá 3.5 triệu đó anh.", "Ok"]


def test_cho_ky_tu_ke_tiep_truoc_khi_cat():
    s = SpeechSegmenter()
    assert s.push("Xin chào anh nhé.") == []  # chưa biết là hết câu hay "nhé.5"
    assert s.push(" Hì") == ["Xin chào anh nhé."]


# ---------- lọc chữ cho TTS ----------

def test_bo_emoji_va_ky_hieu_giu_tieng_viet():
    assert clean_for_speech("Chào anh 🎬😊 **nha** ~ ❤️") == "Chào anh nha"
    assert clean_for_speech("Nhưng hơi buồn 🎬.") == "Nhưng hơi buồn."
    assert clean_for_speech("Ừ, được! Giá 50% thôi.") == "Ừ, được! Giá 50% thôi."
    assert clean_for_speech("👍👍") == ""


# ---------- qua API ----------

def samples(event):
    raw = base64.b64decode(event["pcm"])
    return list(struct.unpack(f"<{len(raw) // 2}h", raw))


def test_audio_theo_doan_va_manh_dung_thu_tu_va_cam_xuc():
    tts = FakeTTS()
    evs = chat(["[happy] Chào anh, em đang nghe nhạc", " đó. [sad] Nhưng hơi buồn", " 🎬."], tts)

    audio = [e for e in evs if e["type"] == "audio"]
    assert [(a["seq"], a["part"]) for a in audio] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    heads = [a for a in audio if a["part"] == 0]
    assert [(a["text"], a["emotion"]) for a in heads] == [
        ("Chào anh, em đang nghe nhạc đó.", "happy"),
        ("Nhưng hơi buồn.", "sad"),
    ]
    assert all("text" not in a for a in audio if a["part"] > 0)  # chữ chỉ đi kèm mảnh đầu
    assert all(a["rate"] == 1000 for a in audio)
    assert samples(audio[1]) == [1000] * 4  # mảnh sau giữ nguyên
    assert samples(audio[0])[0] == 0  # mảnh đầu được fade-in
    assert evs[-1]["type"] == "done"  # done chỉ đến sau khi đã có đủ audio


def test_chen_khoang_nghi_sau_moi_doan():
    evs = chat(["[happy] Câu thứ nhất đây anh.", " Câu thứ hai nữa nè."], FakeTTS(pause=0.01))
    audio = [e for e in evs if e["type"] == "audio"]
    assert [(a["seq"], a["part"]) for a in audio] == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
    assert samples(audio[2]) == [0] * 10  # 0,01s x 1000Hz


def test_chu_khong_cho_giong():
    """Engine giả chỉ chịu tạo giọng khi LLM đã phát hết chữ. Nếu chữ phải chờ giọng thì hai bên chờ nhau
    -> hết giờ -> tts_error; tạo giọng chạy nền thì không có lỗi và đủ audio."""
    done = threading.Event()
    evs = chat(["[happy] Câu thứ nhất đây anh.", " Câu thứ hai nữa nè.", " Câu thứ ba luôn."], FakeTTS(wait_for=done), done=done)
    assert not [e for e in evs if e["type"] == "tts_error"]
    assert len([e for e in evs if e["type"] == "audio" and e["part"] == 0]) == 3
    assert evs[-1]["type"] == "done"


def test_bao_xong_chu_truoc_khi_doc_xong_giong():
    evs = chat(["[happy] Câu thứ nhất đây anh.", " Câu thứ hai nữa nè."], FakeTTS())
    types = [e["type"] for e in evs]
    assert types.count("text_done") == 1 and types[-1] == "done"
    text_done = evs[types.index("text_done")]
    assert text_done == {"type": "text_done", "raw": "[happy] Câu thứ nhất đây anh. Câu thứ hai nữa nè.", "stopReason": "end_turn"}
    # mọi chữ đến trước text_done
    assert all(t != "text" for t in types[types.index("text_done"):])


def test_tu_choi_thi_khong_bao_xong_chu():
    class Refuse(FakeLLM):
        async def stream(self, history, system=None):
            yield ("text", "...")
            yield ("stop", "refusal")

    app.dependency_overrides[get_llm] = lambda: Refuse([])
    app.dependency_overrides[get_tts] = lambda: FakeTTS()
    evs = events(TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": "x"}], "voice": True}).text)
    assert "text_done" not in [e["type"] for e in evs] and evs[-1]["type"] == "error"


def test_fade_in_tang_dan_tu_0():
    pcm = struct.pack("<20h", *([10000] * 20))
    out = list(struct.unpack("<20h", fade_in(pcm, 1000)))  # 10ms ở 1000Hz = 10 mẫu
    assert out[0] == 0 and 0 < out[5] < out[8] < 10000 and out[9:] == [10000] * 11


def test_tat_giong_thi_khong_tao_audio():
    tts = FakeTTS()
    evs = chat(["[happy] Chào anh, em đang nghe nhạc đó."], tts, voice=False)
    assert not [e for e in evs if e["type"] == "audio"]
    assert tts.spoken == []


def test_giong_loi_khong_lam_hong_chu():
    evs = chat(["[happy] Câu thứ nhất đây anh.", " Câu thứ hai nữa nè."], FakeTTS(fail=True))
    assert [e["message"] for e in evs if e["type"] == "tts_error"] == ["giọng hỏng"]
    assert not [e for e in evs if e["type"] == "audio"]
    assert "".join(e["text"] for e in evs if e["type"] == "text") == "Câu thứ nhất đây anh. Câu thứ hai nữa nè."
    assert evs[-1]["type"] == "done"


def test_log_luot_chat_co_do_tre_khong_co_noi_dung(offline_voice_and_log):
    chat(["[happy] Bí mật của anh là gì vậy.", " Kể em nghe đi."], FakeTTS())
    line = offline_voice_and_log.read_text(encoding="utf-8")
    record = json.loads(line)
    assert record["provider"] == "fake" and record["model"] == "fake-model" and record["tts"] == "fake-tts"
    assert record["segments"] == 2 and record["error"] is None and record["tts_error"] is False
    assert record["first_text_ms"] is not None and record["first_audio_ms"] is not None and record["total_ms"] >= 0
    assert "Bí mật" not in line and "Chào em" not in line


# ---------- engine và health ----------

def test_piper_thieu_file_bao_cach_tai(tmp_path):
    tts = PiperTTS(voice_path=tmp_path / "khong-co.onnx")
    assert "scripts/get_voice.py" in tts.check()
    with pytest.raises(TTSError, match="get_voice"):
        list(tts.stream("chào"))


def test_vieneu_chua_cai_thu_vien(monkeypatch):
    monkeypatch.setattr("app.tts.importlib.util.find_spec", lambda name: None)
    assert VieNeuTTS().check() == "Chưa cài thư viện giọng VieNeu. Chạy: uv sync"
    with pytest.raises(TTSError, match="uv sync"):
        list(VieNeuTTS().stream("chào"))


def test_chon_engine_giong(monkeypatch):
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    assert isinstance(make_tts(), VieNeuTTS)  # mặc định
    monkeypatch.setenv("VIENEU_VOICE", "Trúc Ly")
    assert make_tts().voice == "Trúc Ly"
    monkeypatch.setenv("TTS_PROVIDER", "none")
    assert make_tts() is None
    monkeypatch.setenv("TTS_PROVIDER", "piper")
    assert isinstance(make_tts(), PiperTTS)
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    with pytest.raises(ValueError):
        make_tts()


def test_health_bao_trang_thai_giong():
    app.dependency_overrides[get_llm] = lambda: FakeLLM([])
    client = TestClient(app)
    app.dependency_overrides[get_tts] = lambda: FakeTTS()
    assert client.get("/api/health").json()["voice"] == {"engine": "fake-tts", "ok": True, "problem": None}
    app.dependency_overrides[get_tts] = lambda: None
    voice = client.get("/api/health").json()["voice"]
    assert voice["engine"] is None and voice["ok"] is False


def test_piper_chua_cai_thu_vien(tmp_path, monkeypatch):
    """Audit #10: piper-tts (GPL) giờ là phần cài thêm, thiếu thì báo đúng lệnh cài."""
    voice = tmp_path / "giong.onnx"
    voice.write_bytes(b"")
    voice.with_suffix(".onnx.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("app.tts.importlib.util.find_spec", lambda name: None)
    assert "uv sync --extra piper" in PiperTTS(voice_path=voice).check()
