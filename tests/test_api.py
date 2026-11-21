"""Test luồng API bằng LLM giả (không gọi Claude thật, không tốn tiền)."""

import json

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from app.llm import ClaudeLLM
from app.main import app, get_llm


class FakeLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, chunks, stop="end_turn", fail_after=None):
        self.chunks, self.stop, self.fail_after = chunks, stop, fail_after
        self.received = None

    async def stream(self, history, system=None):
        self.received = history
        for i, c in enumerate(self.chunks):
            if self.fail_after is not None and i == self.fail_after:
                raise RuntimeError("mạng rớt")
            yield ("text", c)
        yield ("stop", self.stop)

    async def check(self):
        return None


def sse_events(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use(llm):
    app.dependency_overrides[get_llm] = lambda: llm
    return llm


USER_MSG = {"messages": [{"role": "user", "content": "Chào em"}]}


def test_stream_tach_cam_xuc_va_tra_raw(client):
    use(FakeLLM(["[hap", "py] Chào anh", "! [surprised] Ủa?"]))
    events = sse_events(client.post("/api/chat", json=USER_MSG).text)

    assert [e["emotion"] for e in events if e["type"] == "emotion"] == ["happy", "surprised"]
    assert "".join(e["text"] for e in events if e["type"] == "text") == "Chào anh! Ủa?"
    assert events[-1] == {"type": "done", "raw": "[happy] Chào anh! [surprised] Ủa?", "stopReason": "end_turn"}


def test_refusal_bao_loi(client):
    use(FakeLLM(["..."], stop="refusal"))
    events = sse_events(client.post("/api/chat", json=USER_MSG).text)
    assert events[-1]["type"] == "error"


def test_loi_giua_chung_bao_loi_khong_cat_im_lang(client):
    use(FakeLLM(["[happy] Chào", " anh"], fail_after=1))
    events = sse_events(client.post("/api/chat", json=USER_MSG).text)
    assert events[-1]["type"] == "error"
    assert "mạng rớt" in events[-1]["message"]


def test_tu_choi_message_cuoi_khong_phai_user(client):
    use(FakeLLM([]))
    body = {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}
    assert client.post("/api/chat", json=body).status_code == 422


def test_cat_lich_su_luon_bat_dau_bang_user(client):
    llm = use(FakeLLM(["ok"]))
    turns = [{"role": r, "content": "x"} for r in ["user", "assistant"] * 30] + [{"role": "user", "content": "cuối"}]
    client.post("/api/chat", json={"messages": turns})
    assert len(llm.received) <= 40
    assert llm.received[0]["role"] == "user"
    assert llm.received[-1]["content"] == "cuối"


def test_thieu_api_key_bao_loi_de_hieu(client, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    use(ClaudeLLM())
    events = sse_events(client.post("/api/chat", json=USER_MSG).text)
    assert events[-1]["type"] == "error"
    assert events[-1]["message"].startswith("Chưa có ANTHROPIC_API_KEY")


def test_sai_api_key_bao_loi_tieng_viet(client):
    def unauthorized(req):
        return httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})

    llm = ClaudeLLM()
    # SDK anthropic 2.x dùng httpx2 (không phải httpx)
    llm._client = anthropic.AsyncAnthropic(api_key="sai", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(unauthorized)))
    use(llm)
    events = sse_events(client.post("/api/chat", json=USER_MSG).text)
    assert events[-1] == {"type": "error", "message": "Sai ANTHROPIC_API_KEY. Kiểm tra lại file .env nhé."}


def test_loi_ngoai_du_kien_khong_nhac_api_key(client):
    use(FakeLLM(["a"], fail_after=0))
    message = sse_events(client.post("/api/chat", json=USER_MSG).text)[-1]["message"]
    assert "mạng rớt" in message and "ANTHROPIC" not in message


def test_phuc_vu_frontend(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "importmap" in res.text
    assert client.get("/vendor/three-vrm/three-vrm.module.min.js").status_code == 200
    # model chưa có thì 404 (trang dựa vào đó để hiện hướng dẫn); không dùng waifu.vrm vì máy dev có thể đã có file
    assert client.head("/models/khong-ton-tai.vrm").status_code == 404
    # trình duyệt phải hỏi lại server, không được dùng main.js cũ sau khi cập nhật app
    assert client.get("/main.js").headers["cache-control"] == "no-cache"


def test_luot_cu_qua_dai_khong_khoa_ca_cuoc_tro_chuyen(client):
    """Audit #2: một câu cũ > 4000 ký tự (vd Claude trả lời dài) từng làm mọi lượt sau bị 422 cho tới khi xóa chat."""
    llm = use(FakeLLM(["ok"]))
    turns = [{"role": "user", "content": "kể dài đi"}, {"role": "assistant", "content": "a" * 5000},
             {"role": "user", "content": "tiếp nha"}]
    assert client.post("/api/chat", json={"messages": turns}).status_code == 200
    assert all(len(t["content"]) <= 4000 for t in llm.received)


def test_tin_moi_qua_dai_van_bao_loi(client):
    use(FakeLLM(["ok"]))
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "a" * 5000}]}).status_code == 422


def test_chan_ten_mien_la_tro_ve_may(client):
    """Audit #5: DNS rebinding, trang lạ trỏ tên miền của nó về 127.0.0.1 để đọc /api/memory."""
    assert TestClient(app, base_url="http://evil.example").get("/api/memory").status_code == 400
    assert TestClient(app, base_url="http://localhost:8000").get("/api/memory").status_code == 200
