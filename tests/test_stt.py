"""Test nghe giọng nói (spec 003) bằng engine giả: không cần mic, Whisper hay mạng."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_llm, get_stt
import numpy as np

from app import stt as stt_module
from app.stt import SAMPLE_RATE, STTError, WhisperSTT, ZipformerSTT, keep_segment, make_stt, normalize_transcript


class FakeSTT:
    name = "fake-stt"

    def __init__(self, text="chào em", fail=None):
        self.text = text
        self.fail = fail
        self.received = None

    def transcribe(self, pcm16):
        if self.fail:
            raise self.fail
        self.received = pcm16
        return self.text

    def check(self):
        return None

    def warm_up(self):
        pass

    def info(self):
        return {"model": "fake", "device": "cpu"}


def pcm(seconds, odd=False):
    return bytes(int(SAMPLE_RATE * seconds) * 2 + (1 if odd else 0))


def post(body, stt):
    app.dependency_overrides[get_stt] = lambda: stt
    return TestClient(app).post("/api/stt", content=body, headers={"Content-Type": "application/octet-stream"})


def test_nhan_dang_tra_chu_va_do_dai():
    stt = FakeSTT("chào em")
    res = post(pcm(1.5), stt)
    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "chào em" and body["audio_ms"] == 1500 and body["ms"] >= 0
    assert stt.received == pcm(1.5)  # nhận nguyên PCM, không qua mã hóa


def test_khong_nghe_thay_gi_thi_chu_rong():
    res = post(pcm(1.0), FakeSTT(""))
    assert res.status_code == 200 and res.json()["text"] == ""


@pytest.mark.parametrize(
    ("body", "status", "phrase"),
    [
        (b"", 400, "quá ngắn"),
        (pcm(0.1), 400, "quá ngắn"),
        (pcm(1.0, odd=True), 400, "byte lẻ"),
        (pcm(31), 413, "30 giây"),
    ],
)
def test_tu_choi_am_thanh_khong_hop_le(body, status, phrase):
    stt = FakeSTT()
    res = post(body, stt)
    assert res.status_code == status and phrase in res.json()["detail"]
    assert stt.received is None  # không tốn công nhận dạng


def test_engine_loi_bao_tieng_viet():
    res = post(pcm(1.0), FakeSTT(fail=STTError("Không nạp được Whisper")))
    assert res.status_code == 500 and res.json()["detail"] == "Không nạp được Whisper"
    res = post(pcm(1.0), FakeSTT(fail=RuntimeError("boom")))
    assert res.status_code == 500 and res.json()["detail"].startswith("Không nhận dạng được giọng nói")


def test_tat_stt_thi_bao_503():
    res = post(pcm(1.0), None)
    assert res.status_code == 503 and "STT_PROVIDER=none" in res.json()["detail"]


def test_log_khong_chua_am_thanh_hay_noi_dung(offline_voice_and_log):
    post(pcm(1.0), FakeSTT("bí mật của anh"))
    record = json.loads(offline_voice_and_log.read_text(encoding="utf-8"))
    assert record["kind"] == "stt" and record["audio_ms"] == 1000 and record["chars"] == len("bí mật của anh")
    assert "bí mật" not in json.dumps(record, ensure_ascii=False)


# ---------- bộ lọc câu bịa: số lấy từ lần đo thật (spikes/audio/bench_stt.py) ----------

def test_bo_cau_bia_khi_chi_co_tieng_on():
    # ồn trắng / ù 50Hz: Whisper bịa "Hãy subscribe cho kênh..." với no_speech_prob cao nhưng logprob cao
    assert not keep_segment(0.89, -0.28, 0.9, "Hãy subscribe cho kênh Ghiền Mì Gõ")
    assert not keep_segment(0.93, -0.29, 0.9, "")
    assert not keep_segment(0.3, -0.3, 0.9, "Cảm ơn các bạn đã theo dõi")  # câu bịa quen thuộc
    assert not keep_segment(0.1, -0.3, 3.0, "em em em em em em em em")  # lặp


def test_giu_cau_noi_that_ke_ca_khi_whisper_hoi_khong_chac():
    assert keep_segment(0.01, -0.44, 0.8, "Chào em, hôm nay em thế nào?")
    assert keep_segment(0.58, -0.76, 0.8, "Chào em hôm nay em thề nạo")  # giọng Trúc Ly, nói thật
    assert keep_segment(0.41, -0.67, 0.8, "Mặc nằm vào bị sếp mắng")


# ---------- engine và health ----------

def test_chon_engine_nghe(monkeypatch):
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    assert isinstance(make_stt(), ZipformerSTT)  # mặc định: tiếng Việt, ít sai và nhanh hơn Whisper
    monkeypatch.setenv("STT_PROVIDER", "whisper")
    assert isinstance(make_stt(), WhisperSTT)
    monkeypatch.setenv("WHISPER_THREADS", "6")
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    stt = make_stt()
    assert stt.threads == 6 and stt.compute_type == "float16" and stt.info() == {"model": "small", "device": "cuda"}
    monkeypatch.setenv("STT_PROVIDER", "none")
    assert make_stt() is None
    monkeypatch.setenv("STT_PROVIDER", "google")
    with pytest.raises(ValueError):
        make_stt()


def test_health_bao_trang_thai_nghe():
    class Brain:
        provider, model = "fake", "fake"

        async def check(self):
            return None

    app.dependency_overrides[get_llm] = lambda: Brain()
    client = TestClient(app)
    app.dependency_overrides[get_stt] = lambda: FakeSTT()
    assert client.get("/api/health").json()["stt"] == {"engine": "fake-stt", "model": "fake", "device": "cpu", "ok": True, "problem": None}
    app.dependency_overrides[get_stt] = lambda: None
    ears = client.get("/api/health").json()["stt"]
    assert ears["engine"] is None and ears["ok"] is False


# ---------- Zipformer ----------

def test_chuan_hoa_chu_in_hoa_cua_zipformer():
    assert normalize_transcript("CHÀO EM  HÔM NAY EM THẾ NÀO") == "Chào em hôm nay em thế nào"
    assert normalize_transcript("   ") == ""


def test_zipformer_thieu_model_bao_cach_tai(tmp_path, monkeypatch):
    monkeypatch.setenv("ZIPFORMER_DIR", str(tmp_path))
    engine = ZipformerSTT()
    problem = engine.check()
    assert "get_stt_model.py" in problem and "ZIPFORMER_DIR" in problem
    with pytest.raises(STTError, match="get_stt_model"):
        engine.transcribe(pcm(1.0))


class FakeRecognizer:
    """Thay sherpa-onnx: ghi lại audio nhận được, trả chữ IN HOA như Zipformer thật."""

    def __init__(self, text):
        self.text, self.audio = text, None

    def create_stream(self):
        rec = self

        class Stream:
            result = type("R", (), {"text": rec.text})()

            def accept_waveform(self, rate, audio):
                rec.audio = (rate, audio)

        return Stream()

    def decode_stream(self, stream):
        pass


def test_zipformer_chi_nhan_dang_doan_co_tieng_noi(monkeypatch):
    engine = ZipformerSTT()
    engine._recognizer = FakeRecognizer("MIRA ƠI HÔM NAY EM CÓ VUI KHÔNG")
    # VAD cắt lấy đoạn có tiếng nói: chỉ phần đó được đưa cho model
    monkeypatch.setattr(stt_module, "speech_only", lambda audio: audio[100:200])
    assert engine.transcribe(pcm(1.0)) == "Mira ơi hôm nay em có vui không"
    rate, audio = engine._recognizer.audio
    assert rate == SAMPLE_RATE and len(audio) == 100


def test_zipformer_khong_co_tieng_noi_thi_khong_doan(monkeypatch):
    # Đo thật: không chặn thì Zipformer đọc im lặng/tiếng ồn thành "Và", "Đây", "Tôi"
    engine = ZipformerSTT()
    engine._recognizer = FakeRecognizer("VÀ")
    monkeypatch.setattr(stt_module, "speech_only", lambda audio: audio[:0])
    assert engine.transcribe(pcm(1.0)) == ""
    assert engine._recognizer.audio is None  # không gọi model


def test_vad_that_bo_im_lang_va_tieng_on():
    # Silero VAD thật (đi kèm faster-whisper, không cần mạng): im lặng và nhiễu trắng không có tiếng nói
    rng = np.random.default_rng(0)
    assert stt_module.speech_only(np.zeros(SAMPLE_RATE * 2, dtype=np.float32)).size == 0
    assert stt_module.speech_only(rng.normal(0, 0.05, SAMPLE_RATE * 2).astype(np.float32)).size == 0
