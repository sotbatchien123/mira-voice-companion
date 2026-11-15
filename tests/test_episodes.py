"""Test trí nhớ sâu hơn (spec 009): tóm tắt buổi trò chuyện cũ, bỏ sự kiện đã qua lâu."""

import asyncio
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.episodes import Episode, EpisodeStore, parse_summary, render_episodes, summary_messages
from app.main import app, get_episodes, get_llm, get_memory, get_presence
from app.memory import MemoryStore, system_prompt
from app.presence import Presence

NOW = datetime(2026, 11, 14, 21, 30)
SUMMARY = "Anh kể mèo Mướp bị ốm, anh định đưa Mướp đi khám thú y ngày mai."


class FakeLLM:
    provider, model = "fake", "fake-model"

    def __init__(self, summary=SUMMARY, gate=None):
        self.summary = summary
        self.gate = gate  # asyncio.Event: giữ model "đang tóm tắt" để thử lượt chen vào
        self.complete_calls = []
        self.system = None

    async def stream(self, history, system=None):
        self.system = system
        yield ("text", "[happy] Dạ anh!")
        yield ("stop", "end_turn")

    async def complete(self, messages, *, json_mode=False, max_tokens=256):
        self.complete_calls.append(messages[0]["content"])
        if self.gate:
            await self.gate.wait()
        if "CUỘC TRÒ CHUYỆN" in messages[0]["content"]:
            return json.dumps({"tom_tat": self.summary}, ensure_ascii=False)
        return '{"facts": []}'

    async def check(self):
        return None

    async def warm_up(self):
        pass


@pytest.fixture
def store(tmp_path):
    return EpisodeStore(tmp_path / "episodes.json")


def chat_session(store, at=NOW - timedelta(days=1)):
    store.record("user", "Con mèo Mướp nhà anh bị ốm, bỏ ăn từ hôm qua.", at)
    store.record("assistant", "Tội Mướp quá, anh đưa bé đi khám chưa?", at)
    store.record("user", "Chưa, mai anh định đưa đi thú y gần nhà.", at + timedelta(minutes=2))


# ---------- tóm tắt ----------

def test_buoi_ket_thuc_khi_im_qua_lau(store):
    assert not store.due(NOW)  # chưa có gì
    chat_session(store, NOW - timedelta(minutes=10))
    assert not store.due(NOW)
    assert store.due(NOW + timedelta(minutes=30))


def test_tom_tat_luu_lai_va_mo_buoi_moi(store, tmp_path):
    chat_session(store)
    llm = FakeLLM()
    result = asyncio.run(store.close(llm))
    assert result == {"summarized": True, "turns": 3}
    assert "Anh: Con mèo Mướp" in llm.complete_calls[0] and "Mira: Tội Mướp" in llm.complete_calls[0]
    [ep] = store.list()
    assert (ep.date, ep.started, ep.summary) == ("2026-11-13", "21:30", SUMMARY)
    assert not store.due(NOW + timedelta(days=2))  # buổi mới chưa có lượt nào
    again = EpisodeStore(tmp_path / "episodes.json")  # đọc lại từ file
    assert [e.summary for e in again.list()] == [SUMMARY] and again.turns == []


def test_buoi_chi_chao_hoi_thi_khong_goi_model(store):
    store.record("user", "Chào em", NOW)
    store.record("assistant", "Dạ chào anh!", NOW)
    llm = FakeLLM()
    assert asyncio.run(store.close(llm))["summarized"] is False
    assert llm.complete_calls == [] and store.list() == [] and store.turns == []


def test_luot_moi_chen_vao_luc_dang_tom_tat_khong_mat(store):
    chat_session(store)

    async def run():
        gate = asyncio.Event()
        task = asyncio.create_task(store.close(FakeLLM(gate=gate)))
        await asyncio.sleep(0)
        store.record("user", "Anh về rồi nè", NOW)  # lượt mới trong lúc model đang tóm tắt
        assert (await store.close(FakeLLM()))["summarized"] is False  # không tóm tắt chồng
        gate.set()
        await task

    asyncio.run(run())
    assert len(store.list()) == 1
    assert store.turns == [("user", "Anh về rồi nè")]


def test_quen_het_luc_dang_tom_tat_khong_hoi_sinh(store):
    """Bấm "Quên hết" trong lúc model đang tóm tắt: bản tóm tắt không được ghi lại, lượt nói sau khi xóa vẫn còn."""
    chat_session(store)

    async def run():
        gate = asyncio.Event()
        task = asyncio.create_task(store.close(FakeLLM(gate=gate)))
        await asyncio.sleep(0)
        store.clear()
        store.record("user", "Anh mới nói sau khi xóa", NOW)
        gate.set()
        return await task

    assert asyncio.run(run())["summarized"] is False
    assert store.list() == []
    assert store.turns == [("user", "Anh mới nói sau khi xóa")]
    assert EpisodeStore(store.path).list() == []  # file cũng không có


def test_hen_tom_tat_sau_khoang_im(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_GAP_MINUTES", "0")
    store = EpisodeStore(tmp_path / "episodes.json")
    chat_session(store)
    results = []

    async def run():
        store.close_later(FakeLLM(), on_done=results.append)
        store.close_later(FakeLLM(), on_done=results.append)  # hẹn lại: hẹn cũ bị hủy
        await asyncio.sleep(0.05)

    asyncio.run(run())
    assert results == [{"summarized": True, "turns": 3}]


def test_doc_ket_qua_model_hong():
    assert parse_summary("không phải json") == ""
    assert parse_summary('{"tom_tat": "  Anh   kể  chuyện. "}') == "Anh kể chuyện."
    assert parse_summary("[1, 2]") == ""


def test_buoi_qua_dai_chi_dua_doan_cuoi():
    turns = [("user", "x" * 100)] * 100
    prompt = summary_messages(turns)[0]["content"]
    assert len(prompt) < 7000 and "..." in prompt


def test_hien_thi_moi_nhat_truoc_doi_ngay_tuong_doi():
    eps = [Episode(str(i), f"2026-11-{d:02d}", "20:00", s) for i, (d, s) in enumerate([
        (1, "Buổi rất cũ."), (10, "Anh kể chuyện công ty."), (12, "Anh nói thứ Sáu này đi phỏng vấn ở FPT."),
        (13, SUMMARY)])]
    text = render_episodes(eps, NOW)
    lines = text.splitlines()
    assert len(lines) == 3 and "Buổi rất cũ" not in text
    assert lines[0].startswith("- hôm qua (buổi tối 13/11): Anh kể mèo Mướp")
    assert "ngày 14/11/2026" in lines[0] and lines[0].endswith("(là hôm nay)")  # "ngày mai" của hôm qua
    assert lines[1].startswith("- 2 ngày trước") and "thứ Sáu ngày 13/11/2026" in lines[1]
    assert lines[1].endswith("(đã diễn ra)")


def test_system_prompt_co_phan_tom_tat():
    prompt = system_prompt(NOW, [], "- hôm qua (buổi tối 13/11): " + SUMMARY)
    assert "Các lần trò chuyện gần đây" in prompt and SUMMARY in prompt
    assert "Các lần trò chuyện gần đây" not in system_prompt(NOW, [])


# ---------- bỏ sự kiện cũ ----------

def test_bo_su_kien_da_qua_lau(tmp_path):
    mem = MemoryStore(tmp_path / "memory.json")
    mem.add([("su_kien", "Anh đi phỏng vấn ở FPT thứ Sáu này")], "2026-10-20")  # 23/10: qua 22 ngày
    mem.add([("su_kien", "Anh đi khám răng ngày mai")], "2026-11-05")  # 06/11: mới qua 8 ngày
    mem.add([("su_kien", "Anh từng đi Đà Lạt")], "2026-01-01")  # không có ngày: giữ
    mem.add([("so_thich", "Anh thích xem phim ngày 01/01/2020")], "2026-01-01")  # không phải sự kiện: giữ
    mem.add([("su_kien", "Anh có hẹn ngày 31/02/2026")], "2026-01-01")  # ngày không tồn tại: không làm hỏng
    assert mem.expire_events(NOW) == 1
    assert [f.text for f in mem.facts()] == ["Anh đi khám răng ngày mai", "Anh từng đi Đà Lạt",
                                             "Anh thích xem phim ngày 01/01/2020", "Anh có hẹn ngày 31/02/2026"]
    assert [f.text for f in MemoryStore(tmp_path / "memory.json").facts()][0] == "Anh đi khám răng ngày mai"
    assert mem.expire_events(NOW) == 0


# ---------- qua API ----------

def use(llm, store, presence):
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_episodes] = lambda: store
    app.dependency_overrides[get_presence] = lambda: presence


def test_api_chat_ghi_lai_buoi_dang_noi(store, tmp_path):
    use(FakeLLM(), store, Presence(tmp_path / "presence.json"))
    res = TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": "Anh về rồi nè em"}]})
    assert res.status_code == 200
    assert store.turns == [("user", "Anh về rồi nè em"), ("assistant", "Dạ anh!")]  # không lưu tag cảm xúc


def test_api_chat_tin_dau_buoi_moi_khong_bi_gop_vao_buoi_cu(store, tmp_path):
    """Buổi hôm qua chưa tóm tắt (server vừa bật lại), anh nhắn tin mới: tin đó mở buổi mới, không lọt vào tóm tắt cũ."""
    chat_session(store)
    llm = FakeLLM()
    use(llm, store, Presence(tmp_path / "presence.json"))
    res = TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": "Hôm nay anh được thăng chức"}]})
    assert res.status_code == 200
    summary_prompt = next(c for c in llm.complete_calls if "CUỘC TRÒ CHUYỆN" in c)
    assert "thăng chức" not in summary_prompt and "Con mèo Mướp" in summary_prompt
    assert [e.summary for e in store.list()] == [SUMMARY]
    assert store.turns == [("user", "Hôm nay anh được thăng chức"), ("assistant", "Dạ anh!")]


def test_api_chao_tom_tat_buoi_truoc_roi_moi_chao(store, tmp_path, monkeypatch):
    chat_session(store)  # buổi hôm qua, server tắt trước khi kịp tóm tắt
    llm = FakeLLM()
    use(llm, store, Presence(tmp_path / "presence.json"))
    res = TestClient(app).post("/api/proactive", json={"kind": "greet", "messages": []})
    assert res.status_code == 200
    assert [e.summary for e in store.list()] == [SUMMARY]
    assert SUMMARY.split(",")[0] in llm.system  # lời chào đã thấy bản tóm tắt
    assert store.turns == [("assistant", "Dạ anh!")]  # lời chào mở đầu buổi mới; lời nhắc ẩn không bị ghi


def test_api_xem_xoa_buoi_tro_chuyen(store, tmp_path):
    chat_session(store)
    asyncio.run(store.close(FakeLLM()))
    mem = MemoryStore(tmp_path / "memory.json")
    app.dependency_overrides[get_memory] = lambda: mem
    app.dependency_overrides[get_episodes] = lambda: store
    client = TestClient(app)
    [ep] = client.get("/api/memory").json()["episodes"]
    assert ep["summary"] == SUMMARY
    assert client.delete("/api/memory/episodes/khong-co").status_code == 404
    assert client.delete(f"/api/memory/episodes/{ep['id']}").json() == {"ok": True}
    assert client.get("/api/memory").json()["episodes"] == []
    chat_session(store)
    asyncio.run(store.close(FakeLLM()))
    client.delete("/api/memory")  # quên hết: cả tóm tắt
    assert store.list() == []
