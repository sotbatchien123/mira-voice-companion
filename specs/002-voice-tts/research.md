# Research: 002-voice-tts

Số liệu đầy đủ: `spikes/audio/KET_QUA.md` (đo 2026-11-13 trên RTX 5070 Laptop 8GB, i7-14650HX).

## R1. Engine giọng

**Quyết định**: Piper `vi_VN-vais1000-medium`.

- CPU, RTF ≈ 0,035, audio đầu 0,01–0,04s, VRAM 0, license CC-BY-4.0, đủ dấu thanh (0/267 phoneme bị bỏ).
- Đọc chưa thật rõ (Whisper nghe lại WER 25–38%).

**Phương án khác**:
- F5-TTS tiếng Việt: rõ hơn (WER 8–15%), bắt chước giọng được, nhưng ~1,4s/câu, 1–1,3GB VRAM, phi thương mại,
  và không vừa VRAM cùng `qwen3:8b`. → spec 004.
- Piper `25hours_single`: loại, mất dấu thanh với piper-tts 1.8.
- viXTTS: loại, cần fork TTS cũ không chạy RTX 5070.

## R2. Tách đoạn để đọc sớm

Học từ `faster_first_response` của Open-LLM-VTuber: đoạn đầu cắt ở dấu phẩy đầu tiên nếu đã đủ ~12 ký tự,
các đoạn sau cắt ở `.`, `!`, `?`, `…`, xuống dòng. Đoạn quá ngắn (< 4 ký tự chữ, vd "Ô!") được gộp vào đoạn sau.

## R3. Truyền audio

Event SSE `audio` chứa WAV base64. Một kết nối, thứ tự tự nhiên, không cần endpoint mới. WebSocket chỉ cần khi
có STT hai chiều (spec 003).

## R4. Nhép miệng

Web Audio `AnalyserNode` → RMS của khung hiện tại → `aa` expression. Đơn giản, không cần phân tích âm vị.

## R5. Log độ trễ

JSONL một dòng mỗi lượt (ý từ Langfuse mà Animates dùng, bản tối giản): `first_text_ms`, `first_audio_ms`,
`total_ms`, `segments`, `provider`, `model`, `tts`, `stop`, `error`. Không ghi nội dung.
