# Contract: `POST /api/stt`

**Request**: body là PCM 16-bit little-endian, mono, 16 000 Hz (không header).
`Content-Type: application/octet-stream`.

| Trường hợp | Response |
|---|---|
| Nhận dạng được | `200 {"text": "chào em", "audio_ms": 1820, "ms": 1430}` |
| Chỉ có im lặng / tiếng ồn | `200 {"text": "", ...}` (client báo "Không nghe rõ", không gửi tin) |
| Body rỗng, < 0,2s hoặc số byte lẻ | `400 {"detail": "<câu tiếng Việt>"}` |
| Dài hơn 30 giây | `413 {"detail": "<câu tiếng Việt>"}` |
| Chưa bật STT (`STT_PROVIDER=none`) | `503 {"detail": "<câu tiếng Việt>"}` |
| Engine lỗi | `500 {"detail": "<câu tiếng Việt>"}` |

Âm thanh không được lưu; log `logs/turns.jsonl` thêm dòng `{"kind": "stt", "audio_ms", "ms", "chars", "error"}`.

# Contract: `GET /api/health` (bổ sung)

Thêm `"stt": {"engine": "whisper", "model": "small", "device": "cpu", "ok": true, "problem": null}`.
