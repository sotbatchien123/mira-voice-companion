"""Test OllamaLLM bằng httpx.MockTransport (không cần cài Ollama thật)."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.llm import ClaudeLLM, LLMError, OllamaLLM, make_llm
from app.main import app, get_llm

HISTORY = [{"role": "user", "content": "Chào em"}]


def ndjson(*objs) -> bytes:
    return "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objs).encode()


def collect(llm: OllamaLLM) -> list:
    async def run():
        return [ev async for ev in llm.stream(HISTORY)]

    return asyncio.run(run())


def ollama_with(handler) -> OllamaLLM:
    return OllamaLLM(transport=httpx.MockTransport(handler))


def test_stream_va_payload(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setenv("OLLAMA_THINK", "false")
    seen = {}

    def handler(req: httpx.Request):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, content=ndjson(
            {"message": {"role": "assistant", "content": "[happy] Chào"}, "done": False},
            {"message": {"role": "assistant", "content": " anh!"}, "done": False},
            {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop"},
        ))

    events = collect(ollama_with(handler))

    assert events == [("text", "[happy] Chào"), ("text", " anh!"), ("stop", "end_turn")]
    body = seen["body"]
    assert seen["path"] == "/api/chat"
    assert body["model"] == "qwen3:8b" and body["stream"] is True and body["think"] is False
    assert body["messages"][0]["role"] == "system"  # persona đi đầu
    assert body["messages"][1:] == HISTORY


def test_khong_gui_think_khi_de_trong(monkeypatch):
    monkeypatch.delenv("OLLAMA_THINK", raising=False)
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, content=ndjson({"message": {"content": "ok"}, "done": True, "done_reason": "stop"}))

    collect(ollama_with(handler))
    assert "think" not in seen["body"]


def test_bi_cat_do_het_token():
    def handler(req):
        return httpx.Response(200, content=ndjson({"message": {"content": "dài"}, "done": True, "done_reason": "length"}))

    assert collect(ollama_with(handler))[-1] == ("stop", "max_tokens")


def test_chua_pull_model_bao_lenh_can_chay(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")

    def handler(req):
        return httpx.Response(404, json={"error": "model 'qwen3:8b' not found"})

    with pytest.raises(LLMError, match="ollama pull qwen3:8b"):
        collect(ollama_with(handler))


def test_ollama_chua_bat():
    def handler(req):
        raise httpx.ConnectError("refused", request=req)

    with pytest.raises(LLMError, match="Đã cài và mở Ollama chưa"):
        collect(ollama_with(handler))


def test_loi_giua_stream():
    def handler(req):
        return httpx.Response(200, content=ndjson({"message": {"content": "a"}, "done": False}, {"error": "GPU hết bộ nhớ"}))

    with pytest.raises(LLMError, match="GPU hết bộ nhớ"):
        collect(ollama_with(handler))


def test_ollama_chet_giua_stream():
    class Broken(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield ndjson({"message": {"content": "[happy] Chào"}, "done": False})
            raise httpx.ReadError("connection reset")

    def handler(req):
        return httpx.Response(200, stream=Broken())

    with pytest.raises(LLMError, match="Mất kết nối với Ollama giữa chừng"):
        collect(ollama_with(handler))


def check(llm) -> str | None:
    return asyncio.run(llm.check())


def test_kiem_tra_san_sang(monkeypatch):
    def tags(*names):
        return lambda req: httpx.Response(200, json={"models": [{"name": n} for n in names]})

    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    assert check(ollama_with(tags("qwen3:8b"))) is None
    assert "ollama pull qwen3:8b" in check(ollama_with(tags("llama3:8b")))

    monkeypatch.setenv("OLLAMA_MODEL", "qwen3")
    assert check(ollama_with(tags("qwen3:latest"))) is None  # không ghi tag = :latest

    def down(req):
        raise httpx.ConnectError("refused", request=req)

    assert check(ollama_with(down)).startswith("Không kết nối được Ollama")


def test_claude_kiem_tra_key(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    assert check(ClaudeLLM()).startswith("Chưa có ANTHROPIC_API_KEY")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert check(ClaudeLLM()) is None


def test_health_bao_van_de():
    def down(req):
        raise httpx.ConnectError("refused", request=req)

    try:
        app.dependency_overrides[get_llm] = lambda: ollama_with(down)
        body = TestClient(app).get("/api/health").json()
    finally:
        app.dependency_overrides.clear()
    assert body["ok"] is False and body["provider"] == "ollama"
    assert body["problem"].startswith("Không kết nối được Ollama")


def test_chon_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(make_llm(), OllamaLLM)  # mặc định local
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert isinstance(make_llm(), OllamaLLM)
    monkeypatch.setenv("LLM_PROVIDER", "Claude")
    assert isinstance(make_llm(), ClaudeLLM)
    monkeypatch.setenv("LLM_PROVIDER", "gpt")
    with pytest.raises(ValueError):
        make_llm()


def test_qua_api_tach_tag_va_bao_loi_than_thien():
    """Đi hết đường: Ollama giả -> server -> SSE, và lỗi Ollama hiện nguyên câu tiếng Việt."""

    def ok(req):
        return httpx.Response(200, content=ndjson(
            {"message": {"content": "[sad] Anh đi đâu"}, "done": False},
            {"message": {"content": " vậy?"}, "done": True, "done_reason": "stop"},
        ))

    def down(req):
        raise httpx.ConnectError("refused", request=req)

    client = TestClient(app)
    try:
        app.dependency_overrides[get_llm] = lambda: ollama_with(ok)
        text = client.post("/api/chat", json={"messages": HISTORY}).text
        assert '"emotion": "sad"' in text and '"raw": "[sad] Anh đi đâu vậy?"' in text

        app.dependency_overrides[get_llm] = lambda: ollama_with(down)
        last = [l for l in client.post("/api/chat", json={"messages": HISTORY}).text.splitlines() if l][-1]
        assert json.loads(last[6:])["message"].startswith("Không kết nối được Ollama")
    finally:
        app.dependency_overrides.clear()
