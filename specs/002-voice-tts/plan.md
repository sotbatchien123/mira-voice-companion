# Implementation Plan: 002-voice-tts

**Spec**: `specs/002-voice-tts/spec.md` · **Research**: `research.md` · **Số liệu**: `spikes/audio/KET_QUA.md`

## Summary

Thêm Piper TTS chạy CPU vào server. Chữ sạch từ `EmotionTagParser` đi qua bộ tách đoạn (`SpeechSegmenter`),
lọc ký tự không đọc được, tạo WAV bằng Piper trong thread riêng, rồi gửi thành event `audio` trong luồng SSE.
Frontend xếp hàng phát bằng Web Audio API và dùng `AnalyserNode` lấy âm lượng để nhép miệng. Mỗi lượt ghi
một dòng `logs/turns.jsonl`.

## Technical Context

- Python 3.12 + uv; thêm dependency `piper-tts>=1.8` (lý do: TTS tiếng Việt chạy CPU, nhanh nhất trong số đo).
- Frontend JS thuần, Web Audio API (không thêm thư viện).
- Model giọng: `models/piper/vi_VN-vais1000-medium.onnx` (+ `.onnx.json`), tải bằng `scripts/get_voice.py`.
- Hiệu năng đo được: Piper RTF ≈ 0,035, audio đầu ≈ 0,02–0,04s mỗi đoạn. VRAM: 0.

## Constitution Check

| Nguyên tắc | Đánh giá |
|---|---|
| I. Bộ não thay thế được | TTS có hợp đồng riêng `SpeechEngine` (`synthesize`, `check`), `make_tts()` theo `TTS_PROVIDER`. Server không rẽ nhánh theo tên engine. |
| II. Độ trễ | Đoạn đầu cắt ở dấu phẩy; Piper nhanh nên tạo audio ngay trong luồng (xem đánh đổi bên dưới). Có log để đo. |
| III. Local-first | Piper chạy CPU, không mạng. Log không chứa nội dung chat. Model giọng không vào git. |
| IV. Test offline | Segmenter, lọc chữ, SSE có audio, log, `PiperTTS.check()` đều test bằng fake, không cần file giọng. |
| V. Đơn giản | Một dependency mới; audio đi chung SSE thay vì thêm endpoint/WebSocket. |
| Ràng buộc: SSE là hợp đồng | Thêm event `audio`, `tts_error`; request thêm `voice`; health thêm `voice`. Cập nhật cả 2 phía, README, test. |
| Ràng buộc: VRAM | 0 MiB thêm. |

## Đánh đổi đã chọn

- **Tạo audio ngay trong generator SSE** (không dùng worker nền): Piper mất ~0,1s cho câu 3s nên chữ chỉ trễ rất
  ít. Khi đổi sang F5-TTS (~1,4s/câu) phải chuyển sang worker nền để chữ không bị chặn — ghi lại cho spec 004.
- **Base64 WAV trong SSE**: tốn thêm ~33% băng thông nhưng chạy local nên không đáng kể; đổi lại giữ đúng thứ tự
  chữ/audio/cảm xúc mà không cần đồng bộ hai kênh.

## Structure

```
app/speech_text.py   SpeechSegmenter + clean_for_speech()
app/tts.py           SpeechEngine (Protocol), PiperTTS, make_tts()
app/turn_log.py      ghi logs/turns.jsonl
app/main.py          chat(): segment → synthesize → event audio; health thêm voice
web/audio_player.js  hàng đợi phát + AnalyserNode
web/main.js          nút bật/tắt giọng, gắn player vào avatar
web/avatar.js        setMouthLevel() khi có audio thật
scripts/get_voice.py tải model Piper
```

## Bổ sung 2026-11-13: VieNeu + stream + worker nền

Số liệu: `spikes/audio/KET_QUA.md` (VieNeu fp32 trên i7-14650HX: audio đầu 0,23s, mảnh 0,32s, RTF ~0,45, nạp 7,5s;
tự có ~0,06s lặng đầu và ~0,24–0,37s lặng cuối mỗi câu; int8 không nhanh hơn rõ nên giữ fp32).

- Hợp đồng `SpeechEngine` đổi: `stream(text) -> Iterator[bytes]` (PCM 16-bit mono), `sample_rate`,
  `segment_pause_s` (khoảng nghỉ thêm sau mỗi đoạn: Piper 0,25s, VieNeu 0 vì đã có sẵn).
- `Speaker` thành worker nền: LLM đẩy đoạn vào hàng đợi, worker tạo giọng trong thread và đẩy từng mảnh vào hàng đợi
  chung; generator SSE chỉ đọc hàng đợi chung. `done` gửi sau khi worker xong để client nhận đủ audio.
- Fade-in 10ms ở mảnh đầu mỗi đoạn để không bật "tách".
- Event `audio` mới: `{seq, part, rate, pcm, text?, emotion?}` (`text`, `emotion` chỉ ở `part` 0). Client tạo
  `AudioBuffer` thẳng từ PCM, bỏ `decodeAudioData`.
- Dependency mới: `vieneu` (torch-free trên CPU). Constitution I, II, III, V: giữ hợp đồng chung, giảm độ trễ,
  chạy local, không thêm VRAM.
- Đánh đổi: request mở lâu hơn (tới khi tạo xong giọng, ~0,45× thời lượng audio); nút gửi khóa trong lúc đó.
