import io
import wave

import httpx
import pytest

from app.tts import TTSError, VoicevoxTTS, make_tts


def _wav(samples: int = 100, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * samples)
    return buf.getvalue()


def _moras(*vowels: str) -> list[dict]:
    return [{"text": "x", "vowel": v} for v in vowels]


def _engine(speakers: list[str], phrases=None) -> VoicevoxTTS:
    phrases = phrases or [{"moras": _moras("o", "a", "e", "N")}]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/audio_query":
            return httpx.Response(200, json={"accent_phrases": phrases, "outputSamplingRate": 24000})
        if request.url.path == "/synthesis":
            speakers.append(request.url.params["speaker"])
            return httpx.Response(200, content=_wav())
        if request.url.path == "/version":
            return httpx.Response(200, json="0.26.2")
        return httpx.Response(404)

    return VoicevoxTTS(transport=httpx.MockTransport(handler))


def test_voicevox_tong_hop_va_nguyen_am():
    speakers: list[str] = []
    tts = _engine(speakers)
    pcm, vowels = tts.synthesize("おかえり", "happy")
    assert len(pcm) == 200
    assert vowels == "oaen"
    assert speakers == ["1"]
    assert b"".join(tts.stream("おかえり")) == pcm


def test_voicevox_nguyen_am_cl_va_nghi():
    phrases = [{"moras": _moras("a", "cl", "i"), "pause_mora": {"text": "、", "vowel": "pau"}}, {"moras": _moras("u")}]
    _, vowels = _engine([], phrases).synthesize("あっい、う")
    assert vowels == "a-i-u"


def test_voicevox_cam_xuc_mac_dinh(monkeypatch):
    speakers: list[str] = []
    tts = _engine(speakers)
    tts.synthesize("a")
    tts.synthesize("a", "relaxed")
    assert speakers == ["3", "3"]

    monkeypatch.setenv("VOICEVOX_EMOTION_STYLES", "sad:76,hỏng,angry:x")
    speakers.clear()
    tts = _engine(speakers)
    tts.synthesize("a", "sad")
    tts.synthesize("a", "happy")
    assert speakers == ["76", "3"]


def test_voicevox_chua_bat():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    tts = VoicevoxTTS(transport=httpx.MockTransport(boom))
    problem = tts.check()
    assert "VOICEVOX" in problem and "127.0.0.1:50021" in problem
    with pytest.raises(TTSError):
        tts.synthesize("a")


def test_voicevox_san_sang():
    assert _engine([]).check() is None


def test_chon_engine_voicevox(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "voicevox")
    assert isinstance(make_tts(), VoicevoxTTS)


def test_voicevox_warm_up_tong_hop_thu():
    speakers: list[str] = []
    _engine(speakers).warm_up()
    assert speakers == ["3"]


def test_voicevox_warm_up_bao_loi_khi_chua_bat():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(TTSError):
        VoicevoxTTS(transport=httpx.MockTransport(boom)).warm_up()


def test_voicevox_nguyen_am_vo_thanh_viet_hoa():
    # VOICEVOX ghi nguyên âm vô thanh bằng chữ hoa (です -> "U"); miệng vẫn phải mấp máy
    _, vowels = _engine([], [{"moras": _moras("e", "U", "N", "I")}]).synthesize("です")
    assert vowels == "euni"


def test_voicevox_nho_trang_thai_tat_bat():
    up = {"ok": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if not up["ok"]:
            raise httpx.ConnectError("refused")
        if request.url.path == "/audio_query":
            return httpx.Response(200, json={"accent_phrases": []})
        if request.url.path == "/synthesis":
            return httpx.Response(200, content=_wav())
        return httpx.Response(200, json="0.26.2")

    tts = VoicevoxTTS(transport=httpx.MockTransport(handler))
    assert tts.down is False  # chưa biết thì cứ thử nói
    with pytest.raises(TTSError):
        tts.synthesize("a")
    assert tts.down is True
    up["ok"] = True
    assert tts.check() is None and tts.down is False
