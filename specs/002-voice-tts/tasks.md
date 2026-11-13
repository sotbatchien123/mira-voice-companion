# Tasks: 002-voice-tts

## Phase 1: Setup

- [x] T001 Thêm `piper-tts>=1.8` vào `pyproject.toml`, `uv lock`
- [x] T002 [P] `scripts/get_voice.py` tải `vi_VN-vais1000-medium` vào `models/piper/`; `.gitignore` thêm `models/`, `logs/`
- [x] T003 [P] `.env.example`: `TTS_PROVIDER`, `PIPER_VOICE`, `PIPER_LENGTH_SCALE`

## Phase 2: Foundational

- [x] T004 [P] `app/speech_text.py`: `SpeechSegmenter` (đoạn đầu cắt ở dấu phẩy, gộp đoạn quá ngắn) + `clean_for_speech()`
- [x] T005 [P] `app/tts.py`: `SpeechEngine` Protocol, `PiperTTS` (nạp lười, `synthesize` → WAV bytes, `check`), `make_tts()`
- [x] T006 [P] `app/turn_log.py`: ghi 1 dòng JSONL mỗi lượt, không có nội dung

## Phase 3: US1 - Nghe Mira nói (P1)

- [x] T007 [US1] `app/main.py`: `voice` trong request; tạo audio theo đoạn trong `asyncio.to_thread`; event `audio`, `tts_error`; health thêm `voice`
- [x] T008 [P] [US1] Test: segmenter, lọc chữ, SSE có audio đúng thứ tự, `voice=false`, TTS lỗi không hỏng chữ, `PiperTTS.check()` thiếu file
- [x] T009 [US1] `web/audio_player.js`: hàng đợi phát, dừng khi gửi tin mới/xóa chat
- [x] T010 [US1] `web/main.js`: nút bật/tắt giọng (localStorage), gửi `voice`, báo lỗi giọng từ health
- [x] T011 [US1] Kiểm chứng thật: đo audio đầu ≤ 1s (SC-001), VRAM không tăng (SC-002), không đọc emoji (SC-003)
  — `verify_live.py --warmup --voice`: audio đầu 0,51–0,68s (5/5); 0 đoạn có emoji/tag; VRAM +4,78GB < riêng qwen3:8b 5,33GB.
  Trình duyệt: AudioContext `running`, các đoạn phát nối tiếp; gửi tin mới dừng 6 đoạn đang phát/chờ; tắt giọng → `voice:false`, 0 đoạn phát, nhớ qua tải lại trang.
  **Chưa nghe bằng tai.**

## Phase 4: US2 - Nhép miệng (P2)

- [x] T012 [US2] `web/avatar.js`: `setMouthLevel()`; player đẩy RMS vào avatar; đổi cảm xúc khi đoạn bắt đầu phát
- [x] T013 [US2] Kiểm chứng: mức âm lượng thay đổi khi phát (đo bằng JS). Nhìn miệng trên VRM thật: cần file `.vrm`
  — Trên `Mira.vrm` với giọng Mỹ Duyên: `aa` tối đa 0,74, mở ở 711 khung hình trong một câu; ảnh chụp thấy miệng mở khi nói.
  — Đã đo: analyser thấy RMS tới 0,49; hệ số miệng chỉnh theo RMS Piper (trung vị 0,17, p90 0,27). Phần nhìn miệng trên VRM còn mở.

## Phase 5: US3 - Log độ trễ (P3)

- [x] T014 [US3] Gắn `turn_log` vào `chat()`; test dòng log có đủ trường, không có nội dung

## Phase 6: Polish

- [x] T015 Cập nhật README, GHI_NHO, contract; `uv run pytest`

## Phase 7: Bổ sung – VieNeu, stream, worker nền

- [x] T016 Thêm `vieneu` vào `pyproject.toml`; `.env(.example)`: `TTS_PROVIDER=vieneu`, `VIENEU_VOICE`, `VIENEU_PRECISION`
- [x] T017 `app/tts.py`: hợp đồng `stream()` + `sample_rate` + `segment_pause_s`; `VieNeuTTS`; `PiperTTS.stream()`
- [x] T018 `app/main.py`: `Speaker` chạy nền, hàng đợi chung, event `audio` dạng PCM theo mảnh, fade-in, khoảng nghỉ
- [x] T019 `web/audio_player.js`: phát PCM theo mảnh; `chat_client.js`/`main.js` theo event mới
- [x] T020 Test: thứ tự mảnh, khoảng nghỉ, chữ không chờ giọng (test khóa chéo), cập nhật test cũ theo contract mới
- [x] T021 Kiểm chứng thật: `verify_live.py --voice` với VieNeu; trình duyệt; VRAM
  — audio đầu 0,53–0,61s (5/5), chữ đầu 0,13–0,15s, 0 đoạn đọc emoji/tag, VRAM không đổi. 100 mảnh / 3 câu: 0 lỗ hổng phát.
  Trình duyệt: 48kHz, nút Gửi mở khi chữ xong lúc giọng còn phát; gửi tin mới dừng 8 mảnh cũ, lịch sử đúng thứ tự.
  Miệng (mô phỏng trên âm lượng thật): mở trung vị 0,32, p90 0,75, khép khi im lặng. **Chưa nhìn trên VRM thật.**
- [x] T022 README, GHI_NHO, contract
- [x] T023 `text_done`: lưu lịch sử + cho gửi tin mới khi chữ xong, không chờ giọng (phát hiện khi đo: câu dài giữ request 28,7s)
- [x] T024 Miệng tự cân theo đỉnh âm lượng (VieNeu RMS trung vị 0,11, nhỏ hơn Piper 0,19)
