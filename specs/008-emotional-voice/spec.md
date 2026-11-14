# Feature Specification: Giọng đổi theo cảm xúc

**Feature Branch**: `008-emotional-voice`

**Created**: 2026-11-14

**Status**: Implemented (chờ người dùng nghe)

**Input**: Người dùng: "làm 2 cái này đi" (giọng đổi theo cảm xúc + trí nhớ sâu hơn).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Câu vui nghe tươi, câu buồn nghe chùng (Priority: P1)

Mira nói "[happy] Thật hả anh? Em vui quá!": giọng có tiếng cười nhẹ ở đầu và nhanh/cao hơn chút. Câu "[sad]": có tiếng
thở dài và chậm/trầm hơn chút. Câu trung tính đọc như cũ.

**Acceptance Scenarios**:

1. Tiếng cười/thở dài không lặp mỗi câu: mỗi loại tối đa 1 lần trong 120s.
2. Chữ hiện trên màn hình và lịch sử không có "[cười]".
3. Engine không hiểu tín hiệu (Piper) thì không chèn (Piper sẽ đọc to nguyên chữ).
4. Tắt từng núm trong `.env`.

### Edge Cases

- Tag cảm xúc đến ngay sau dấu chấm: câu trước vẫn đọc bằng cảm xúc cũ (trước đây bộ tách câu chờ 1 ký tự nên câu
  trước bị gán cảm xúc mới → tiếng thở dài rơi nhầm vào câu vui). Mảnh có nhiều tag, tag bị cắt đôi: đều đúng.

## Đo trước (spike `spikes/audio/emotion_voice.py`, giọng Mỹ Duyên)

VieNeu v3 Turbo chỉ có 3 tín hiệu phi ngôn ngữ: `[cười]`, `[thở dài]`, `[hắng giọng]`; không có tham số tốc độ (cách đọc
lấy từ giọng mẫu). `[cười]` thêm ~0,9s, `[thở dài]` thêm ~0,5s; Zipformer không nghe ra chữ "cười" (là tiếng thật).
Thời gian tạo +0,4s cho đoạn có tín hiệu (mảnh đầu vẫn stream sớm).

## Requirements *(mandatory)*

- **FR-001**: `app/voice_style.py`: `VoiceStyle.cue(emotion)` có thời gian chờ, `speed_for(emotion)`.
- **FR-002**: Speaker chèn tín hiệu vào chữ gửi TTS (không vào chữ hiển thị); event `audio` mảnh đầu có `speed` khi ≠ 1.
- **FR-003**: Trình duyệt phát cả đoạn bằng `playbackRate = speed` (đổi cả tốc độ lẫn cao độ, không tốn CPU server).
- **FR-004**: Tag cảm xúc là ranh giới đoạn đọc (`ParsedChunk.marks`, `SpeechSegmenter.cut()`).
- **FR-005**: `VOICE_EMOTION_CUES`, `VOICE_CUE_COOLDOWN_SECONDS`, `VOICE_EMOTION_SPEED`.

## Success Criteria *(mandatory)*

- **SC-001**: Test offline pass (thời gian chờ, ranh giới tag với 3 kiểu chia mảnh, Piper không bị chèn).
- **SC-002**: Chạy thật: câu vui có `[cười]` đúng 1 lần, event có `speed`, không lộ tín hiệu ra chữ.
- **SC-003**: Người dùng nghe mẫu và chấp nhận (chưa có).
