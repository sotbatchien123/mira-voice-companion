# Feature Specification: Trí nhớ dài hạn của Mira

**Feature Branch**: `004-long-term-memory`

**Created**: 2026-11-14

**Status**: Implemented

**Input**: Người dùng muốn Mira nhớ mình qua nhiều ngày (tên, sở thích, chuyện đã kể), không chỉ 40 lượt gần nhất
trong trình duyệt, và không bị Ollama cắt lịch sử khi chat dài.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mira nhớ điều anh kể, kể cả sau khi xóa chat (Priority: P1)

Người dùng kể "Anh tên Khoa, nuôi mèo tên Mướp". Hôm sau (hoặc sau khi bấm Xóa chat) hỏi "Em còn nhớ mèo của anh
tên gì không?", Mira trả lời đúng.

**Independent Test**: Kể 3 điều, xóa chat, hỏi lại: Mira trả lời đúng cả 3.

**Acceptance Scenarios**:

1. **Given** người dùng kể điều về bản thân, **When** lượt chat xong, **Then** điều đó được lưu (chạy nền, không làm
   chậm câu trả lời).
2. **Given** điều cũ không còn đúng (chuyển nhà, đổi việc), **When** người dùng kể điều mới, **Then** điều cũ được thay,
   không giữ cả hai.
3. **Given** chỉ chào hỏi hoặc hỏi Mira, **When** lượt chat xong, **Then** không lưu gì.
4. Mira chỉ nhắc điều đã nhớ khi liên quan, không bịa thêm.

### User Story 2 - Xem và xóa điều Mira nhớ (Priority: P2)

Người dùng mở bảng "Mira nhớ gì", thấy từng điều kèm ngày, xóa được từng điều hoặc xóa hết.

### User Story 3 - Chat dài không bị cắt ngầm (Priority: P3)

Lịch sử gửi cho model được cắt theo ngân sách ký tự để tổng prompt vừa ngữ cảnh 4096 token, thay vì để Ollama tự cắt
mất phần đầu (gồm cả tính cách nhân vật).

### Edge Cases

- Model trả JSON hỏng, sai loại, hoặc câu rỗng: bỏ qua phần hỏng, không làm lỗi chat.
- Model trích sai/bịa: người dùng xóa được trong bảng; model KHÔNG được tự xóa điều cũ (spike: model 8B xóa bừa).
- Mốc thời gian tương đối ("tuần sau"): giữ nguyên chữ + code ghi ngày người dùng nói (spike: model tính ngày sai).
- File trí nhớ hỏng: bắt đầu lại rỗng, không chặn app.

## Requirements *(mandatory)*

- **FR-001**: Sau mỗi lượt, trích "điều đáng nhớ" từ tin của người dùng bằng chính model đang dùng, chạy song song với
  việc tạo giọng, không chặn chữ.
- **FR-002**: Mỗi điều có loại từ danh sách cố định; loại chỉ một giá trị (tên, tuổi, nghề, nơi ở, cách gọi) thì điều
  mới thay điều cũ; loại khác cộng dồn, trùng thì bỏ, tối đa 60 điều.
- **FR-003**: Mỗi lượt, system prompt có ngày giờ hiện tại và danh sách điều đã nhớ (giới hạn độ dài).
- **FR-004**: Lịch sử gửi model được cắt theo ngân sách ký tự, luôn bắt đầu bằng lượt người dùng.
- **FR-005**: Trí nhớ lưu ở máy (`data/memory.json`, không vào git); xem/xóa được qua API và giao diện; tắt được bằng cấu hình.
- **FR-006**: Log không chứa nội dung điều nhớ.

## Success Criteria *(mandatory)*

- **SC-001**: Kể 3 điều → xóa chat → hỏi lại: Mira đúng ≥ 3/3 lần với qwen3:8b.
- **SC-002**: Chào hỏi/câu hỏi thuần không sinh điều nhớ nào (0 điều trên 4 câu thử).
- **SC-003**: Chuyển nơi ở: còn đúng 1 điều về nơi ở.
- **SC-004**: Độ trễ chữ đầu không tăng quá 0,1s so với trước (trích xuất chạy sau khi chữ xong).
- **SC-005**: Test offline pass, không cần Ollama.

## Assumptions

- Một người dùng trên một máy (không phân tài khoản).
- Trích xuất dùng chính "não" đang chạy; khi dùng Claude thì mỗi lượt tốn thêm một lời gọi nhỏ.
