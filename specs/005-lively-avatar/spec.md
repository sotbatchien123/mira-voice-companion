# Feature Specification: Mira sinh động hơn (nhép miệng theo nguyên âm, cử động đầu)

**Feature Branch**: `005-lively-avatar`

**Created**: 2026-11-14

**Status**: Implemented

**Input**: Model VRM của Mira (VRoid) có sẵn khẩu hình `aa/ih/ou/ee/oh` nhưng app mới dùng `aa`. Muốn miệng khớp từng
âm tiết tiếng Việt và đầu cử động tự nhiên khi nói, khi nghe, theo cảm xúc.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Miệng tạo hình theo nguyên âm (Priority: P1)

Khi Mira nói "Chào anh, em vui lắm", miệng lần lượt tạo hình gần đúng a, a, e, u, a… theo từng âm tiết, đổi đúng
lúc có âm tiết mới trong audio, độ mở theo âm lượng.

**Acceptance Scenarios**:

1. Mỗi âm tiết được gán một khẩu hình từ nguyên âm chính (bỏ dấu thanh: ă/â→a, ê→e, ô/ơ→o, ư→u, y→i; bỏ âm đệm
   "qu", "gi", "o/u" trong "oa/oe/uy/uê").
2. Khẩu hình chuyển sang âm tiết kế khi audio có nhịp âm tiết mới (âm lượng vọt lên sau một khoảng nhỏ).
3. Không có giọng (tắt giọng) thì giữ khẩu hình giả lập như cũ.

### User Story 2 - Đầu cử động khi nói và theo cảm xúc (Priority: P2)

1. Khi nói: đầu gật nhẹ theo nhịp âm tiết.
2. Theo cảm xúc: vui → nghiêng đầu nhẹ; buồn → cúi nhẹ; ngạc nhiên → ngửa nhẹ; giận → hơi chúi tới; chuyển mượt.
3. Khi người dùng đang nói vào mic: Mira nghiêng đầu "lắng nghe".

### Edge Cases

- Chữ không có nguyên âm (số, ký hiệu đã lọc): giữ khẩu hình "aa".
- Âm tiết đếm được nhiều/ít hơn số nhịp trong audio: hết danh sách thì giữ khẩu hình cuối; không chặn phát.
- Model VRM thiếu khẩu hình nào: bỏ qua khẩu hình đó (three-vrm bỏ qua tên không có).

## Requirements *(mandatory)*

- **FR-001**: Logic nguyên âm và bắt nhịp là hàm thuần trong `web/lipsync.js`, kiểm chứng được trên trình duyệt.
- **FR-002**: Không thêm thư viện, không thêm việc cho server; chỉ dùng chữ của đoạn (event `audio` part 0) và âm lượng.
- **FR-003**: Biên độ cử động nhỏ (≤ ~0,15 rad) để không lố; mọi chuyển động có làm mượt (damping).

## Success Criteria *(mandatory)*

- **SC-001**: Trên giọng Mỹ Duyên thật, số nhịp âm tiết bắt được / số âm tiết trong chữ nằm trong 0,7–1,3 ở ≥ 4/5 đoạn.
- **SC-002**: Khi nói, ít nhất 3/5 khẩu hình được dùng; khi im lặng, mọi khẩu hình về 0.
- **SC-003**: Góc cổ/đầu thay đổi theo cảm xúc và khi lắng nghe (đo bằng hook trên trang, `?debug=1`).
- **SC-004**: 86 test Python vẫn pass; không lỗi console.
