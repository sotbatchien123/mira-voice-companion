"""Test Mira chủ động (spec 006): quyết định chào/hỏi thăm, lời nhắc ẩn, lịch sử bắt đầu bằng Mira."""

import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import ChatTurn, app, get_llm, get_memory, get_presence, trim_history
from app.memory import MemoryStore
from app.presence import Presence, describe_gap, proactive_prompt

NOW = datetime(2026, 11, 14, 21, 30)


class FakeLLM:
    provider, model = "fake", "fake-model"

    def __init__(self):
        self.history = None
        self.extract_calls = 0

    async def stream(self, history, system=None):
        self.history = history
        yield ("text", "[happy] Chào anh! Anh về rồi à?")
        yield ("stop", "end_turn")

    async def complete(self, messages, *, json_mode=False, max_tokens=256):
        self.extract_calls += 1
        return '{"facts": []}'

    async def check(self):
        return None

    async def warm_up(self):
        pass


def events(res):
    return [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]


def setup(presence, llm=None, memory=None):
    llm = llm or FakeLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_presence] = lambda: presence
    app.dependency_overrides[get_memory] = lambda: memory
    return TestClient(app), llm


# ---------- quyết định chào / hỏi thăm ----------

def test_mo_ta_khoang_vang():
    assert describe_gap(None, NOW).startswith("chưa từng nói chuyện")
    assert describe_gap(NOW - timedelta(minutes=12), NOW) == "khoảng 12 phút trước"
    assert describe_gap(NOW - timedelta(hours=3, minutes=10), NOW) == "khoảng 3 tiếng trước"
    assert describe_gap(NOW - timedelta(days=1, hours=2), NOW) == "khoảng 1 ngày trước"
    assert describe_gap(NOW - timedelta(days=5), NOW) == "khoảng 5 ngày trước"


def test_chi_chao_khi_vang_du_lau(tmp_path, monkeypatch):
    monkeypatch.setenv("GREET_MIN_GAP_MINUTES", "30")
    p = Presence(tmp_path / "presence.json")
    assert p.should_greet(NOW)  # lần đầu gặp
    p.user_spoke(NOW - timedelta(minutes=10))
    assert not p.should_greet(NOW)
    p.user_spoke(NOW - timedelta(minutes=45))
    assert p.should_greet(NOW)
    p.greeted(NOW - timedelta(minutes=5))  # vừa chào xong (tải lại trang)
    assert not p.should_greet(NOW)


def test_tat_chao_va_hoi_tham(tmp_path, monkeypatch):
    monkeypatch.setenv("PROACTIVE_GREETING", "false")
    monkeypatch.setenv("PROACTIVE_CHECKIN_MINUTES", "0")
    p = Presence(tmp_path / "presence.json")
    p.user_spoke(NOW - timedelta(days=3))
    assert not p.should_greet(NOW) and not p.should_check_in(NOW)


def test_hoi_tham_khi_im_du_lau(tmp_path, monkeypatch):
    monkeypatch.setenv("PROACTIVE_CHECKIN_MINUTES", "10")
    p = Presence(tmp_path / "presence.json")
    assert not p.should_check_in(NOW)  # chưa nói gì thì là việc của lời chào
    p.user_spoke(NOW - timedelta(minutes=4))
    assert not p.should_check_in(NOW)
    p.user_spoke(NOW - timedelta(minutes=11))
    assert p.should_check_in(NOW)


def test_luu_xuong_dia(tmp_path):
    path = tmp_path / "presence.json"
    Presence(path).user_spoke(NOW)
    assert Presence(path).last_user_at == NOW
    path.write_text("{hỏng", encoding="utf-8")
    assert Presence(path).last_user_at is None


def test_loi_nhac_khong_lo_va_khong_chao_lai_khi_hoi_tham():
    greet = proactive_prompt("greet", NOW - timedelta(days=1), NOW)
    check = proactive_prompt("checkin", NOW - timedelta(minutes=12), NOW)
    assert "khoảng 1 ngày trước" in greet and "MỘT chuyện" in greet
    assert "im lặng đã khoảng 12 phút" in check and "KHÔNG chào lại" in check
    assert all("không nhắc tới ứng dụng" in p for p in (greet, check))


# ---------- lịch sử bắt đầu bằng Mira ----------

def test_lich_su_bat_dau_bang_loi_chao():
    turns = [ChatTurn(role="assistant", content="Chào anh!"), ChatTurn(role="user", content="Chào em")]
    assert trim_history(turns) == [{"role": "user", "content": "(anh mở trang)"},
                                   {"role": "assistant", "content": "Chào anh!"}, {"role": "user", "content": "Chào em"}]


def test_gop_hai_loi_mira_lien_nhau():
    turns = [ChatTurn(role="assistant", content="Chào anh!"), ChatTurn(role="assistant", content="Anh đang bận à?"),
             ChatTurn(role="user", content="Ừ")]
    roles = [t["role"] for t in trim_history(turns)]
    assert roles == ["user", "assistant", "user"]
    assert trim_history(turns)[1]["content"] == "Chào anh!\nAnh đang bận à?"


# ---------- qua API ----------

def test_chao_khi_mo_trang_roi_khong_chao_lai(tmp_path):
    presence = Presence(tmp_path / "presence.json")
    presence.user_spoke(NOW - timedelta(days=2))
    client, llm = setup(presence)
    res = client.post("/api/proactive", json={"kind": "greet", "messages": []})
    evs = events(res)
    assert evs[-1]["type"] == "done" and evs[-1]["raw"].startswith("[happy] Chào anh")
    # lời nhắc là lượt "user" tạm cuối cùng, không do người dùng gửi
    assert llm.history[-1]["role"] == "user" and "Ghi chú hệ thống" in llm.history[-1]["content"]
    assert client.post("/api/proactive", json={"kind": "greet", "messages": []}).status_code == 204  # tải lại trang


def test_loi_chu_dong_khong_bi_trich_lam_tri_nho(tmp_path):
    presence = Presence(tmp_path / "presence.json")
    store = MemoryStore(tmp_path / "memory.json")
    client, llm = setup(presence, memory=store)
    events(client.post("/api/proactive", json={"kind": "greet", "messages": []}))
    assert llm.extract_calls == 0 and store.facts() == []


def test_hoi_tham_chi_khi_im_du_lau(tmp_path, monkeypatch):
    monkeypatch.setenv("PROACTIVE_CHECKIN_MINUTES", "10")
    presence = Presence(tmp_path / "presence.json")
    client, _ = setup(presence)
    history = [{"role": "user", "content": "Anh đang code"}, {"role": "assistant", "content": "[happy] Cố lên anh!"}]
    presence.user_spoke(datetime.now() - timedelta(minutes=2))
    assert client.post("/api/proactive", json={"kind": "checkin", "messages": history}).status_code == 204
    presence.user_spoke(datetime.now() - timedelta(minutes=15))
    assert events(client.post("/api/proactive", json={"kind": "checkin", "messages": history}))[-1]["type"] == "done"


def test_chat_ghi_lai_luc_nguoi_dung_noi(tmp_path):
    presence = Presence(tmp_path / "presence.json")
    client, _ = setup(presence)
    client.post("/api/chat", json={"messages": [{"role": "user", "content": "Chào em"}]})
    assert presence.last_user_at is not None and datetime.now() - presence.last_user_at < timedelta(seconds=5)


def test_health_bao_cau_hinh_chu_dong(tmp_path, monkeypatch):
    monkeypatch.setenv("PROACTIVE_CHECKIN_MINUTES", "7")
    client, _ = setup(Presence(tmp_path / "presence.json"))
    assert client.get("/api/health").json()["proactive"] == {"greeting": True, "checkin_minutes": 7}
