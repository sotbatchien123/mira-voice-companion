# Implementation Plan: 004-long-term-memory

**Spec**: `specs/004-long-term-memory/spec.md` · **Spike**: `spikes/memory_extract.py`

## Số đo từ spike (qwen3:8b, think=false)

- System prompt hiện tại: 364 token. Tiếng Việt ~2,1 ký tự/token (một câu 76 ký tự = 36 token).
- Ngữ cảnh Ollama 4096 token, không tăng được (KV cache thêm ~0,6GB mỗi 4096 token, VRAM còn ~0,7GB).
  Ngân sách: system + ngày ~400, trí nhớ ≤ 1200 ký tự (~570 token), trả lời 512 → lịch sử ≤ ~5000 ký tự (~2400 token).
- Trích xuất JSON (`format: "json"`, temperature 0,2): 0,2–2,1s, trung vị 0,67s.
- Lần 1 cho model tự liệt kê điều "outdated": model xóa bừa điều không liên quan → bỏ hẳn.
- Lần 2 model chỉ gán loại, code tự thay theo loại: 7/9 đúng, thay nơi ở đúng; sót 1 ý trong câu 2 ý; tính sai ngày.

## Thiết kế

- `ChatLLM.stream(history, system=...)`: server tự dựng system prompt (persona + ngày giờ + trí nhớ) thay vì provider
  tự gắn persona. Thêm `ChatLLM.complete(messages, json_mode)` cho lời gọi ngắn không stream.
- `app/memory.py`: `MemoryStore` (JSON, ghi nguyên tử), luật cập nhật theo loại, `render_memory()`, prompt + parser
  trích xuất, `extract_facts()`.
- `app/main.py`: `trim_history` theo ngân sách ký tự; sau `text_done` chạy trích xuất song song với `Speaker`, `done`
  gửi sau khi cả hai xong (không có task mồ côi, test xác định được); `GET/DELETE /api/memory`.
- Frontend: nút "Trí nhớ" mở `<dialog>` liệt kê điều nhớ, nút "Quên" từng điều và "Quên hết".

## Constitution Check

| Nguyên tắc | Đánh giá |
|---|---|
| I. Thay thế được | `complete()` thêm vào hợp đồng, cả Ollama và Claude đều có; server không rẽ nhánh theo provider. |
| II. Độ trễ | Trích xuất chạy sau `text_done`, song song với TTS; không đụng chữ đầu. |
| III. Local & riêng tư | `data/memory.json` ở máy, gitignored; log chỉ số lượng; người dùng xem/xóa được. |
| IV. Test offline | Fake LLM `complete()`; store, parser, render, trim đều test thuần. |
| V. Đơn giản | Một file JSON, không DB/vector search; danh sách điều nhớ nhỏ (≤ 60) đưa thẳng vào prompt. |

## Đánh đổi

- Không dùng vector search/RAG: với ≤ 60 điều ngắn, đưa hết vào prompt đơn giản và đủ; khi trí nhớ lớn hơn mới cần.
- Không tóm tắt hội thoại cũ (rolling summary): điều đáng nhớ đã được trích riêng; tóm tắt để sau nếu thấy thiếu.
