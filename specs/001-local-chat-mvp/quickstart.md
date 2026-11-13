# Quickstart & kiểm chứng: 001-local-chat-mvp

## Chuẩn bị

1. `uv sync`
2. Cài Ollama (`winget install Ollama.Ollama`), rồi `ollama pull qwen3:8b`
3. Copy `.env.example` thành `.env` (mặc định `LLM_PROVIDER=ollama`)
4. (Tùy chọn) đặt model nhân vật vào `web/models/waifu.vrm`

## Kiểm chứng tự động

```bash
uv run pytest
```

Kỳ vọng: tất cả pass, không cần mạng/GPU/key (SC-004).

## Kiểm chứng với model thật

```bash
uv run uvicorn app.main:app --port 8000
```

| Bước | Kỳ vọng | Liên quan |
|---|---|---|
| `GET /api/health` | `provider: ollama`, `model: qwen3:8b` | FR-009 |
| Gửi 5 câu tiếng Việt khác nhau (sau câu đầu để nạp model) | Chữ đầu ≤ 2 giây ở ≥ 4/5 câu | SC-001 |
| Xem event SSE của 5 câu đó | ≥ 4/5 câu có ít nhất một event `emotion`, chữ tiếng Việt tự nhiên | SC-002 |
| Xem khung chat | Không có `[happy]`… lộ ra | SC-003 |
| Tắt Ollama rồi gửi tin | Hiện "Không kết nối được Ollama…" | SC-005 |
| Đặt `OLLAMA_MODEL` thành model chưa pull rồi gửi tin | Hiện lệnh `ollama pull …` | SC-005 |
| Nạp VRM, hỏi câu gây ngạc nhiên | Mặt đổi biểu cảm, miệng mấp máy | US2 |
