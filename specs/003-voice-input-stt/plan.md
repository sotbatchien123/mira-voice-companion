# Implementation Plan: 003-voice-input-stt

**Spec**: `specs/003-voice-input-stt/spec.md` · **Số đo**: `spikes/audio/KET_QUA.md`

## Summary

Trình duyệt ghi âm PCM 16kHz mono bằng `AudioWorklet` (không dùng MediaRecorder để server khỏi phải giải mã
webm/opus qua PyAV, thư viện đã gây lỗi lúc đo). Thả nút (hoặc VAD báo hết câu) thì gửi PCM tới `POST /api/stt`;
server chạy faster-whisper `small` int8 trên CPU, trả chữ; client đưa chữ vào luồng gửi tin như khi gõ.

## Technical Context

- Dependency mới: `faster-whisper` (CTranslate2, chạy CPU int8; có sẵn Silero VAD để cắt im lặng).
- Đo được (spike): `small` CPU int8 ~1,45–1,5s cho câu 2,6–3,7s; GPU float16 0,2–0,3s nhưng VRAM đang chật
  (qwen3:8b + nền ≈ 7,4/8,15GB) và cần thêm thư viện cuBLAS/cuDNN → mặc định CPU, GPU là tùy chọn cấu hình.
- Frontend: `web/mic.js` (AudioWorklet + VAD năng lượng), `web/mic_worklet.js`.

## Constitution Check

| Nguyên tắc | Đánh giá |
|---|---|
| I. Thay thế được | Hợp đồng `SpeechRecognizer` (`transcribe`, `check`, `warm_up`), `make_stt()` theo `STT_PROVIDER`. |
| II. Độ trễ | Gửi PCM thô (không mã hóa/giải mã), `beam_size=1`, nạp model sẵn lúc khởi động. Mục tiêu ≤ 2s trên CPU. |
| III. Local & riêng tư | Âm thanh chỉ ở RAM; không ghi đĩa, log chỉ có độ dài/thời gian. |
| IV. Test offline | `FakeSTT` qua `dependency_overrides`; bộ lọc câu bịa test bằng segment giả. |
| V. Đơn giản | Một endpoint HTTP, không WebSocket; VAD năng lượng phía client, không thêm model VAD trên trình duyệt. |
| Ràng buộc VRAM | 0 MiB thêm (CPU). |

## Đánh đổi

- VAD năng lượng phía client đơn giản nhưng dễ bắt nhầm tiếng ồn lớn; server có thêm Silero VAD của faster-whisper
  và bộ lọc `no_speech_prob` để không gửi câu bịa.
- Ngắt lời khi rảnh tay dựa vào khử tiếng vọng của trình duyệt; ngưỡng được nâng khi Mira đang nói. Không kiểm
  chứng được tự động với loa + mic thật.

## Structure

```
app/stt.py          SpeechRecognizer, WhisperSTT (lọc câu bịa), make_stt()
app/main.py         POST /api/stt (PCM16 16kHz), health thêm stt, log lượt nghe
web/mic_worklet.js  AudioWorkletProcessor gửi khung PCM về main thread
web/mic.js          MicRecorder: bấm-giữ, rảnh tay (VAD năng lượng, pre-roll), giới hạn 30s
web/main.js         nút mic, phím Space, nút Rảnh tay, ngắt giọng Mira khi người dùng nói
```
