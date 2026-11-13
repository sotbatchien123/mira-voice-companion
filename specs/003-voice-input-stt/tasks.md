# Tasks: 003-voice-input-stt

## Phase 1: Setup

- [x] T001 Thêm `faster-whisper` vào `pyproject.toml`; `.env(.example)`: `STT_PROVIDER`, `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE`

## Phase 2: Foundational

- [x] T002 `app/stt.py`: `SpeechRecognizer`, `WhisperSTT` (nạp lười, lock, lọc đoạn `no_speech_prob` cao), `make_stt()`
- [x] T003 `app/main.py`: `POST /api/stt` (giới hạn độ dài, lỗi tiếng Việt), health thêm `stt`, nạp sẵn lúc khởi động, log lượt nghe

## Phase 3: US1 - Bấm giữ để nói (P1)

- [x] T004 [P] `web/mic_worklet.js` + `web/mic.js`: ghi PCM 16kHz, bấm-giữ, giới hạn 30s
- [x] T005 [US1] `web/main.js` + `index.html`: nút mic, phím Space, dừng giọng Mira khi bắt đầu nói, gửi chữ nhận được
- [x] T006 [P] [US1] Test: `/api/stt` (chữ, rỗng, quá dài, byte lẻ, lỗi engine), lọc câu bịa, health
- [x] T007 [US1] Kiểm chứng thật: câu do VieNeu đọc → `/api/stt` (độ trễ, WER), im lặng → rỗng; trình duyệt với mic giả lập
  — `scripts/verify_stt.py`: 1,23–1,35s (5/5), WER trung bình 6%, im lặng/ồn trắng/ù 50Hz → 0 câu bịa.
  Trình duyệt (getUserMedia giả phát WAV): giữ nút → chữ sau 1,25s từ lúc thả → tự gửi, Mira trả lời; mic bị chặn → câu hướng dẫn.
  **Chưa thử với mic thật và giọng người thật.**

## Phase 4: US2 - Rảnh tay (P2)

- [x] T008 [US2] `web/mic.js`: VAD năng lượng (nền nhiễu tự cân, pre-roll 0,3s, hết câu sau 0,8s im), ngưỡng cao hơn khi Mira nói
- [x] T009 [US2] Nút "Rảnh tay" (nhớ lựa chọn), ngắt lời Mira khi người dùng chen vào
- [x] T010 [US2] Kiểm chứng: mic giả lập phát câu nói + khoảng lặng → tự gửi đúng 1 tin
  — Rảnh tay: tự phát hiện và gửi đúng 1 tin. Chen vào lúc Mira đang kể chuyện: 4 mảnh giọng bị dừng, câu mới được gửi.
  **Không kiểm chứng được khử tiếng vọng với loa + mic thật.**

## Phase 5: Polish

- [x] T011 README, GHI_NHO, contract; `uv run pytest`; commit
