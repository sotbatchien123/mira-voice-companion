# Data Model: 001-local-chat-mvp

## ChatTurn (lượt chat)

| Field | Kiểu | Quy tắc |
|---|---|---|
| role | `"user"` \| `"assistant"` | Bắt buộc |
| content | string | 1–4000 ký tự. Lượt `assistant` lưu bản gốc còn tag cảm xúc |

- Request gửi lên MUST kết thúc bằng lượt `user` (nếu không: 422).
- Server chỉ gửi cho LLM tối đa 40 lượt gần nhất, cắt sao cho lượt đầu là `user`.
- Lưu ở localStorage key `waifu-chat-history`. Lỗi giữa chừng thì bỏ lượt `user` chưa có trả lời,
  để lịch sử luôn xen kẽ user/assistant.

## Emotion (cảm xúc)

Một trong: `neutral`, `happy`, `angry`, `sad`, `relaxed`, `surprised` (expression chuẩn VRM 1.0).
Alias được chấp nhận: smile/laugh/blush/shy → happy, pout/annoyed → angry, cry → sad,
calm → relaxed, shock → surprised. Tag lạ giữ nguyên như chữ thường.

Trạng thái trên avatar: cảm xúc mới đặt trọng số 0.8 (chuyển mượt); không có cảm xúc mới trong 6 giây
và không đang nói thì về `neutral`.

## Persona

Tên `Mira`, xưng "em" gọi "anh", câu ngắn 1–3 câu, không markdown/emoji, một tag cảm xúc ở đầu
câu trả lời (xem `app/persona.py`).
