# Contract: `ChatLLM.stream(history)` (`app/llm.py`)

- **Input**: `history`: list `{role, content}` đã được server cắt gọn, bắt đầu bằng `user`, kết thúc bằng `user`.
  System prompt do từng provider tự gắn từ `app/persona.py`.
- **Output**: async iterator gồm:
  - 0..n lần `("text", delta)`: text thô, có thể chứa tag cảm xúc, có thể cắt giữa tag.
  - đúng 1 lần `("stop", reason)` ở cuối, với `reason` đã chuẩn hóa: `end_turn`, `max_tokens`, `refusal`.
- **Lỗi**: lỗi có câu giải thích sẵn thì raise `LLMError(message_tiếng_việt)`; lỗi khác để nguyên,
  server sẽ đổi thành câu dễ hiểu.
- **Thuộc tính**: `provider` (`"claude"` | `"ollama"`), `model` (tên model đang dùng).
- **`check()`** (async): kiểm tra nhanh, không tốn tiền. Trả `None` nếu sẵn sàng, ngược lại là câu tiếng Việt
  nói cách khắc phục. Dùng cho `/api/health`.

Provider hiện có: `ClaudeLLM`, `OllamaLLM`. Chọn bằng `make_llm()` theo `LLM_PROVIDER`.
