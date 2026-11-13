# Feature Specification: Mira nói thành tiếng (TTS local) + nhép miệng theo giọng

**Feature Branch**: `002-voice-tts`

**Created**: 2026-11-13

**Status**: Implemented (còn T013: nhìn miệng trên VRM thật)

**Input**: Người dùng chốt: TTS và STT đều chạy local; làm khâu giọng nói với giọng có sẵn trước, giọng riêng
sau (spec 004). Số liệu đo ở `spikes/audio/KET_QUA.md`. Học thêm từ Open-LLM-VTuber (đọc câu đầu sớm) và
Animates (ghi log độ trễ từng khâu).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nghe Mira trả lời bằng giọng nói (Priority: P1)

Người dùng gửi tin, chữ hiện dần như cũ, và Mira đọc to câu trả lời bằng tiếng Việt. Giọng bắt đầu sớm,
không chờ Mira trả lời xong cả đoạn.

**Why this priority**: Giọng nói là bước lớn nhất từ "khung chat" sang "bạn đồng hành".

**Independent Test**: Bật giọng, gửi "Chào em", nghe giọng tiếng Việt bắt đầu trong thời gian ngắn.

**Acceptance Scenarios**:

1. **Given** giọng đang bật, **When** gửi tin, **Then** âm thanh câu đầu bắt đầu phát trong ≤ 1 giây kể từ
   lúc chữ đầu tiên hiện ra, và các câu sau phát nối tiếp, đúng thứ tự.
2. **Given** câu trả lời có emoji hoặc ký hiệu, **When** Mira đọc, **Then** không đọc emoji/ký hiệu.
3. **Given** người dùng tắt giọng, **When** gửi tin, **Then** không có âm thanh, server không tốn công tạo
   giọng, và lựa chọn này được nhớ qua lần tải lại trang.
4. **Given** đang phát giọng, **When** người dùng gửi tin mới hoặc xóa chat, **Then** giọng cũ dừng ngay.
5. **Given** chưa có file giọng hoặc tạo giọng bị lỗi, **When** gửi tin, **Then** chữ vẫn hiện bình thường
   và trang báo một câu tiếng Việt nói cách khắc phục.

### User Story 2 - Miệng nhép theo giọng thật (Priority: P2)

Khi có giọng, miệng avatar mở/đóng theo âm lượng của audio đang phát, thay cho nhịp giả lập. Biểu cảm
đổi đúng lúc câu tương ứng được đọc.

**Independent Test**: Nạp VRM, bật giọng, quan sát miệng khớp nhịp nói và đứng yên khi im lặng.

**Acceptance Scenarios**:

1. **Given** giọng bật và đang phát audio, **When** có tiếng, **Then** miệng mở theo âm lượng; khi hết
   audio thì miệng khép.
2. **Given** giọng tắt, **When** đang stream chữ, **Then** dùng khẩu hình giả lập như spec 001.

### User Story 3 - Đo được độ trễ từng lượt (Priority: P3)

Mỗi lượt chat được ghi một dòng log gồm thời gian tới chữ đầu, tới audio đầu, tổng thời gian, model,
engine giọng và lỗi (nếu có), để so sánh khi đổi model hoặc engine.

**Acceptance Scenarios**:

1. **Given** server đang chạy, **When** chat 1 lượt, **Then** `logs/turns.jsonl` có thêm 1 dòng JSON với các
   con số trên và **không** chứa nội dung tin nhắn.

### Edge Cases

- Câu rất ngắn ("Ô!") hoặc chỉ có emoji: gộp với câu sau hoặc bỏ qua, không tạo audio rỗng.
- Câu không có dấu kết thúc: đọc phần còn lại khi stream kết thúc.
- Stream lỗi giữa chừng: audio đã gửi vẫn phát, sau đó hiện lỗi như cũ.
- Trình duyệt chặn tự phát âm thanh: audio chỉ bắt đầu sau khi người dùng đã bấm gửi (có tương tác).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Server MUST chuyển câu trả lời thành giọng nói tiếng Việt chạy hoàn toàn trên máy, không dùng GPU.
- **FR-002**: Câu trả lời MUST được tách thành đoạn để đọc: đoạn đầu được cắt sớm ở dấu phẩy đầu tiên nếu đủ dài;
  các đoạn sau theo dấu kết thúc câu.
- **FR-003**: Chữ đưa vào TTS MUST đã bỏ tag cảm xúc, emoji và ký hiệu không đọc được.
- **FR-004**: Audio MUST đi cùng luồng SSE hiện có, theo đúng thứ tự, kèm cảm xúc đang có lúc đoạn đó bắt đầu.
- **FR-005**: Người dùng MUST bật/tắt được giọng; khi tắt, server không tạo audio.
- **FR-006**: Lỗi giọng (thiếu file, lỗi tạo) MUST NOT làm hỏng phần chữ; MUST báo bằng câu tiếng Việt.
- **FR-007**: Engine giọng MUST đi qua một hợp đồng chung để sau đổi sang engine khác (F5-TTS) chỉ bằng cấu hình.
- **FR-008**: Mỗi lượt MUST ghi một dòng log độ trễ, không chứa nội dung hội thoại.
- **FR-009**: Miệng avatar MUST nhép theo âm lượng audio thật khi có giọng.

## Success Criteria *(mandatory)*

- **SC-001**: Với `qwen3:8b` đã nạp, audio đầu tiên tới trình duyệt trong ≤ 1,0 giây kể từ lúc gửi ở ≥ 4/5 lần.
- **SC-002**: VRAM không tăng khi bật giọng (Piper chạy CPU).
- **SC-003**: 0 lần đọc emoji/tag trong 10 câu thử.
- **SC-004**: Test tự động chạy không cần Ollama, GPU, file giọng hay mạng, và pass hết.

## Assumptions

- Giọng mặc định: Piper `vi_VN-vais1000-medium` (CC-BY-4.0), tải về `models/piper/`, không đưa vào git.
- Chưa có STT (spec 003) và giọng riêng (spec 004).
- Avatar VRM vẫn do người dùng cung cấp; thiếu VRM thì vẫn nghe được giọng.

## Bổ sung 2026-11-13: đổi sang VieNeu-TTS (giọng Mỹ Duyên)

Người dùng nghe Piper thấy "cứng, già, khựng" và chọn giọng **Mỹ Duyên** của VieNeu-TTS v3 Turbo sau khi nghe mẫu.

- **FR-010**: Engine mặc định MUST là VieNeu-TTS (CPU/ONNX, không tốn VRAM), giọng chọn bằng cấu hình; Piper vẫn dùng được.
- **FR-011**: Audio MUST được gửi theo từng mảnh ngay khi engine tạo ra (stream), không chờ xong cả đoạn.
- **FR-012**: Tạo giọng MUST chạy song song với luồng chữ: chữ không được chờ giọng.
- **FR-013**: Giữa các câu MUST có khoảng nghỉ tự nhiên; đầu mỗi đoạn không được bật "tách".
- **SC-005**: Audio đầu ≤ 1,0s ở ≥ 4/5 lần (giữ như SC-001) với VieNeu; không có khoảng chờ giữa các mảnh trong một câu.
