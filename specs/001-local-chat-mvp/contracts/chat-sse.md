# Contract: `POST /api/chat`

**Request** (`application/json`):

```json
{ "messages": [ { "role": "user", "content": "Chào em" } ] }
```

Sai định dạng → `422` (FastAPI validation), không mở stream.

**Response** (`text/event-stream`): mỗi event là một dòng `data: <json>` rồi dòng trống.

| type | Trường | Ý nghĩa |
|---|---|---|
| `emotion` | `emotion` | Cảm xúc mới, đổi biểu cảm avatar |
| `text` | `text` | Mảnh chữ đã bỏ tag, nối vào khung chat |
| `done` | `raw`, `stopReason` | Kết thúc; `raw` là câu gốc còn tag để lưu lịch sử |
| `error` | `message` | Kết thúc do lỗi; câu tiếng Việt hiển thị thẳng cho người dùng |

Stream luôn kết thúc bằng đúng một event `done` hoặc `error`. `stopReason: "refusal"` được đổi thành `error`.

# Contract: `GET /api/health`

```json
{ "ok": false, "provider": "ollama", "model": "qwen3:8b", "problem": "Không kết nối được Ollama ở ..." }
```

`ok` cho biết "não" đã sẵn sàng chưa, qua `ChatLLM.check()` của từng provider: Ollama gọi `/api/tags` và xem model đã pull chưa; Claude chỉ xem có key chưa, không gọi API. Khi `ok` là `false`, `problem` là câu tiếng Việt nói cách khắc phục, và trang hiện câu này ngay khi mở. Không có trường riêng cho từng provider (constitution I).

Text trong event `text` đã bỏ tag và bỏ luôn dấu cách ngay sau tag, nên không còn dấu cách đôi.
