# Contract (bổ sung so với 001): `POST /api/chat` và `GET /api/health`

Cập nhật 2026-11-13: audio gửi theo từng mảnh PCM (thay cho WAV cả đoạn), thêm `text_done`.

## Request

```json
{ "messages": [ ... ], "voice": true }
```

`voice` mặc định `false`. Khi `false`, server không tạo audio.

## Event mới trong SSE

| type | Trường | Ý nghĩa |
|---|---|---|
| `audio` | `seq`, `part`, `rate`, `pcm`, `text`*, `emotion`* | Một mảnh giọng nói. `seq` là số đoạn (tăng từ 0), `part` là số mảnh trong đoạn (tăng từ 0); `rate` là tần số mẫu; `pcm` là PCM 16-bit little-endian mono, mã hóa base64. *`text` (chữ được đọc) và `emotion` (cảm xúc lúc đoạn bắt đầu, có thể `null`) chỉ có ở `part` 0 |
| `text_done` | `raw`, `stopReason` | Chữ đã xong (giọng có thể vẫn đang tạo). Client lưu lịch sử và cho gửi tin mới từ lúc này. Không gửi khi bị từ chối |
| `tts_error` | `message` | Tạo giọng lỗi; không kết thúc stream, chữ vẫn tiếp tục. Gửi tối đa 1 lần mỗi lượt |

Thứ tự:
- Các mảnh audio luôn theo đúng `seq`, `part`. Audio chạy song song với chữ, nên có thể xen giữa các event `text`.
- Mọi event `text` đến trước `text_done`.
- Stream vẫn kết thúc bằng đúng một `done` (cùng nội dung với `text_done`, gửi sau khi đã có đủ audio) hoặc `error`.
- Server tự thêm 10ms tăng dần ở đầu mỗi đoạn. Engine không có sẵn khoảng lặng cuối câu (Piper) thì server chèn thêm một mảnh im lặng (`segment_pause_s`).

## Health

```json
{ "ok": true, "provider": "ollama", "model": "qwen3:8b", "problem": null,
  "voice": { "engine": "vieneu", "ok": true, "problem": null } }
```

`ok` ở ngoài chỉ nói về "não". Giọng có `ok`/`problem` riêng để thiếu giọng không chặn chat.
