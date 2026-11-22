"""Spec 011: chế độ giọng tiếng Nhật (VOICEVOX) qua API, dùng LLM và engine giả."""

import json
import re

from fastapi.testclient import TestClient

from app.episodes import EpisodeStore
from app.main import app, get_episodes, get_llm, get_tts
from app.tts import TTSError

CHUNKS = ["[happy] Anh về rồi hả! <ja>おかえ", "り！</ja>"]


class FakeLLM:
    provider = "fake"
    model = "fake-model"

    def __init__(self, chunks=CHUNKS):
        self.chunks = chunks
        self.calls = []

    async def stream(self, history, system=None, max_tokens=None):
        self.calls.append({"history": history, "system": system, "max_tokens": max_tokens})
        for c in self.chunks:
            yield ("text", c)
        yield ("stop", "end_turn")

    async def check(self):
        return None


class FakeJaTTS:
    name = "fake-ja"
    speech_language = "ja"
    credit = "X"
    sample_rate = 24000
    segment_pause_s = 0.0

    def __init__(self, fail=False):
        self.fail = fail
        self.spoken = []

    def synthesize(self, text, emotion=None):
        if self.fail:
            raise TTSError("giọng hỏng")
        self.spoken.append(text)
        return b"\0\0" * 10, "oaei"

    def check(self):
        return None

    def warm_up(self):
        pass


class FakeViTTS:
    name = "fake-vi"
    sample_rate = 1000
    segment_pause_s = 0.0

    def stream(self, text):
        yield b"\0\0"

    def check(self):
        return None

    def warm_up(self):
        pass


def events(body):
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def post(llm, tts, voice=True, messages=None):
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_tts] = lambda: tts
    msgs = messages or [{"role": "user", "content": "Em ơi"}]
    return TestClient(app).post("/api/chat", json={"messages": msgs, "voice": voice})


def test_che_do_nhat_chi_doc_tieng_nhat():
    llm, tts = FakeLLM(), FakeJaTTS()
    evs = events(post(llm, tts).text)
    assert "".join(e["text"] for e in evs if e["type"] == "text") == "Anh về rồi hả!"
    audio = [e for e in evs if e["type"] == "audio"]
    assert len(audio) == 1 and audio[0]["part"] == 0
    assert audio[0]["text"] == "おかえり！"
    assert audio[0]["vowels"] == "oaei"
    assert audio[0]["emotion"] == "happy"
    assert tts.spoken == ["おかえり！"]
    done = next(e for e in evs if e["type"] == "done")
    assert "<ja>" in done["raw"]
    assert llm.calls[0]["max_tokens"] == 1024
    assert "<ja>" in llm.calls[0]["system"]


def test_tat_giong_khong_them_prompt_nhat():
    llm = FakeLLM(["Dạ anh!"])
    post(llm, FakeJaTTS(), voice=False)
    assert "<ja>" not in llm.calls[0]["system"]
    assert llm.calls[0]["max_tokens"] is None


def test_lich_su_cu_bo_tieng_nhat():
    llm = FakeLLM()
    msgs = [{"role": "user", "content": "Chào"}, {"role": "assistant", "content": "Dạ! <ja>はい！</ja>"},
            {"role": "user", "content": "Em ơi"}]
    post(llm, FakeJaTTS(), messages=msgs)
    assert llm.calls[0]["history"][1]["content"] == "Dạ!"


def test_buoi_tro_chuyen_khong_co_tieng_nhat(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.json")
    app.dependency_overrides[get_episodes] = lambda: store
    post(FakeLLM(), FakeJaTTS())
    assistant = [t for r, t in store.turns if r == "assistant"]
    assert assistant == ["Anh về rồi hả!"]
    assert not re.search(r"[\u3040-\u30ff]|<ja>", assistant[0])


def test_health_co_credit():
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_tts] = lambda: FakeJaTTS()
    assert TestClient(app).get("/api/health").json()["voice"]["credit"] == "X"
    app.dependency_overrides[get_tts] = lambda: FakeViTTS()
    assert TestClient(app).get("/api/health").json()["voice"].get("credit") is None


def test_voicevox_loi_van_co_chu():
    evs = events(post(FakeLLM(), FakeJaTTS(fail=True)).text)
    assert "".join(e["text"] for e in evs if e["type"] == "text") == "Anh về rồi hả!"
    assert len([e for e in evs if e["type"] == "tts_error"]) == 1
    assert not [e for e in evs if e["type"] == "audio"]


def test_moi_cau_nhat_dung_cam_xuc_trong_cung_chunk():
    llm, tts = FakeLLM(["[happy] A! <ja>はい</ja> [sad] B. <ja>いや</ja>"]), FakeJaTTS()
    evs = events(post(llm, tts).text)
    audio = [e for e in evs if e["type"] == "audio"]
    assert [(a["text"], a["emotion"]) for a in audio] == [("はい", "happy"), ("いや", "sad")]


def test_luot_toan_tieng_nhat_khong_lot_vao_lich_su():
    llm = FakeLLM()
    msgs = [{"role": "user", "content": "Chào"}, {"role": "assistant", "content": "<ja>はい！</ja>"},
            {"role": "user", "content": "Em ơi"}]
    post(llm, FakeJaTTS(), messages=msgs)
    assert llm.calls[0]["history"][1]["content"] == "…"


def test_ngan_sach_lich_su_tinh_sau_khi_bo_tieng_nhat():
    from app.main import ChatTurn, trim_history

    turns = [ChatTurn(role="user", content="Chào"), ChatTurn(role="assistant", content="Dạ! <ja>" + "あ" * 100 + "</ja>"),
             ChatTurn(role="user", content="Em ơi")]
    assert [t["content"] for t in trim_history(turns, char_budget=20)] == ["Chào", "Dạ!", "Em ơi"]


def test_voicevox_tat_thi_chi_co_chu():
    llm, tts = FakeLLM(["Dạ anh!"]), FakeJaTTS()
    tts.down = True
    evs = events(post(llm, tts).text)
    assert "<ja>" not in llm.calls[0]["system"]  # không bắt model viết tiếng Nhật vô ích
    assert not [e for e in evs if e["type"] in ("audio", "tts_error")]
