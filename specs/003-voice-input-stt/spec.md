# Feature Specification: Nói chuyện với Mira bằng giọng (STT local)

**Feature Branch**: `003-voice-input-stt`

**Created**: 2026-11-14

**Status**: Implemented (chưa thử mic thật)

**Input**: Người dùng chốt STT chạy local bằng faster-whisper `small`. Mục tiêu là nói chuyện như với Ani:
nói vào mic thay vì gõ, và có thể ngắt lời Mira khi cô ấy đang nói. Số đo ở `spikes/audio/KET_QUA.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bấm giữ để nói (Priority: P1)

Người dùng giữ nút mic (hoặc giữ phím Space khi không gõ chữ), nói tiếng Việt, thả ra. Câu nói hiện thành tin
nhắn của người dùng và được gửi cho Mira như khi gõ.

**Why this priority**: Cách nói chắc chắn nhất, không bắt nhầm tiếng ồn hay giọng của chính Mira.

**Independent Test**: Giữ nút, nói "Chào em", thả ra: tin "Chào em" hiện ra và Mira trả lời bằng giọng.

**Acceptance Scenarios**:

1. **Given** đã cho phép mic, **When** giữ nút, nói, rồi thả, **Then** chữ nhận dạng hiện trong ≤ 2 giây kể từ lúc
   thả (câu ≤ 5 giây) và được gửi đi.
2. **Given** Mira đang nói, **When** người dùng bắt đầu giữ nút, **Then** giọng Mira dừng ngay.
3. **Given** bấm rồi thả quá nhanh hoặc chỉ có im lặng, **When** thả, **Then** không gửi gì, báo nhẹ "Không nghe
   rõ" và không tạo tin rỗng.
4. **Given** trình duyệt bị chặn mic hoặc máy không có mic, **When** bấm, **Then** báo câu tiếng Việt nói cách bật mic.

### User Story 2 - Rảnh tay (Priority: P2)

Người dùng bật chế độ "Rảnh tay": app tự nghe, tự nhận ra lúc bắt đầu và kết thúc câu nói, rồi gửi đi.

**Independent Test**: Bật rảnh tay, nói một câu rồi im: câu được gửi sau khi im khoảng 0,8 giây.

**Acceptance Scenarios**:

1. **Given** đang rảnh tay, **When** người dùng nói rồi im ~0,8 giây, **Then** câu được gửi.
2. **Given** đang rảnh tay và Mira đang nói, **When** người dùng chen vào nói, **Then** Mira dừng (ngắt lời).
3. **Given** đang rảnh tay, **When** chỉ có giọng Mira phát từ loa, **Then** không tự gửi giọng của Mira (dùng
   khử tiếng vọng của trình duyệt + ngưỡng cao hơn khi Mira đang nói).
4. Lựa chọn rảnh tay được nhớ qua lần tải lại trang, nhưng mic chỉ mở sau khi người dùng bấm.

### Edge Cases

- Whisper "bịa" câu khi chỉ có tiếng ồn (vd "Hãy subscribe cho kênh…"): đoạn có xác suất không phải tiếng nói
  cao bị bỏ.
- Câu quá dài: cắt ở 30 giây.
- Đang chờ chữ của lượt trước: tin nói vẫn được xử lý như tin gõ (chờ hoặc ngắt theo luật hiện có).

## Requirements *(mandatory)*

- **FR-001**: Nhận dạng tiếng Việt MUST chạy hoàn toàn trên máy, mặc định trên CPU (không thêm VRAM).
- **FR-002**: Có bấm-giữ-để-nói bằng nút và phím Space.
- **FR-003**: Có chế độ rảnh tay với phát hiện đầu/cuối câu nói.
- **FR-004**: Người dùng bắt đầu nói MUST dừng giọng Mira đang phát.
- **FR-005**: Âm thanh ghi âm MUST NOT được lưu xuống đĩa hay log; log chỉ ghi độ dài và thời gian xử lý.
- **FR-006**: Engine nhận dạng MUST đi qua hợp đồng chung để đổi engine/thiết bị chỉ bằng cấu hình.
- **FR-007**: Lỗi (chưa có mic, engine lỗi) MUST báo bằng câu tiếng Việt.

## Success Criteria *(mandatory)*

- **SC-001**: Câu ≤ 5 giây: chữ có trong ≤ 2 giây kể từ lúc thả nút (CPU) ở ≥ 4/5 lần.
- **SC-002**: Với giọng đọc rõ, sai ≤ 15% số từ (đo bằng giọng tổng hợp; giọng thật qua mic laptop cần người dùng thử).
- **SC-003**: Im lặng / tiếng ồn: 0 tin rỗng hay câu bịa được gửi.
- **SC-004**: VRAM không tăng khi bật STT.
- **SC-005**: Test tự động không cần mic, model hay mạng.

## Assumptions

- Trình duyệt Chromium/Edge trên Windows, có `getUserMedia` với `echoCancellation`.
- Mic laptop; chất lượng thật phụ thuộc phòng và mic, không đo được tự động.

## Bổ sung 2026-11-14: đổi sang Zipformer (học từ dự án VoiceDeck)

Người dùng thử mic thật thấy Whisper còn nhận sai. Dự án VoiceDeck của người dùng dùng Zipformer-30M-RNNT-6000h
(tiếng Việt, sherpa-onnx). Đo trên giọng người thật (FLEURS, 40 câu): Zipformer sai 9,2% / 0,27s, Whisper 23,2% / 2,68s.

- **FR-008**: Engine mặc định MUST là Zipformer; Whisper giữ làm dự phòng (`STT_PROVIDER=whisper`).
- **FR-009**: Trước khi nhận dạng MUST lọc bằng Silero VAD: Zipformer cũng đọc im lặng/tiếng ồn thành một từ ("Và", "Đây").
- **FR-010**: VAD rảnh tay theo VoiceDeck (ngưỡng tối thiểu 0,008, cần ≥ 0,18s tiếng nói, hết câu sau 0,7s im);
  ghi âm không bật lọc ồn của trình duyệt.
