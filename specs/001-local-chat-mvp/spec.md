# Feature Specification: Chat với nhân vật 3D bằng "não" chạy local

**Feature Branch**: `001-local-chat-mvp`

**Created**: 2026-11-13

**Status**: In Progress (đã xây phần lớn trước khi áp dụng Spec Kit; spec này ghi lại phạm vi và bước kiểm chứng còn lại)

**Input**: User description: "Waifu chatbot 3D kiểu Grok Ani, hướng web Three.js + VRM, chạy bằng Python, không phụ thuộc API: dùng model local qua Ollama, và test thật."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trò chuyện bằng chữ với nhân vật, không cần API (Priority: P1)

Người dùng mở trang web trên máy mình, gõ tin nhắn tiếng Việt và nhận câu trả lời của nhân vật
hiện dần từng chữ. Toàn bộ chạy trên máy, không cần tài khoản hay API key.

**Why this priority**: Đây là giá trị cốt lõi. Không có hội thoại thì avatar chỉ là hình trưng bày.

**Independent Test**: Bật "não" local, mở trang, gửi "Chào em", thấy câu trả lời tiếng Việt hiện dần,
đúng tính cách nhân vật, không có tag thô như `[happy]` lộ ra.

**Acceptance Scenarios**:

1. **Given** "não" local đang chạy và model đã tải, **When** người dùng gửi tin nhắn, **Then** chữ đầu
   tiên hiện ra trong vòng 2 giây (khi model đã nạp sẵn) và câu trả lời hiện dần đến hết.
2. **Given** đã có vài lượt chat, **When** người dùng tải lại trang, **Then** lịch sử vẫn còn và nhân
   vật nhớ ngữ cảnh khi trả lời tiếp.
3. **Given** "não" local chưa bật hoặc chưa tải model, **When** người dùng gửi tin, **Then** trang hiện
   một câu tiếng Việt nói rõ nguyên nhân và cách khắc phục, không treo.

---

### User Story 2 - Nhân vật thể hiện cảm xúc trên mặt (Priority: P2)

Khi nhân vật trả lời, gương mặt avatar 3D đổi biểu cảm (vui, buồn, giận, ngạc nhiên, thư giãn) theo
nội dung câu trả lời, miệng mấp máy trong lúc "nói", và tự dịu về bình thường sau một lúc.

**Why this priority**: Đây là thứ khiến nhân vật có cảm giác "sống", khác một khung chat thường.

**Independent Test**: Nạp một model VRM, hỏi một câu gây ngạc nhiên hoặc buồn, quan sát mặt avatar
đổi biểu cảm tương ứng.

**Acceptance Scenarios**:

1. **Given** đã nạp model VRM, **When** câu trả lời mang cảm xúc, **Then** avatar đổi sang biểu cảm
   tương ứng trong lúc câu trả lời đang hiện.
2. **Given** model "não" quên hoặc dùng sai nhãn cảm xúc, **When** câu trả lời hiện ra, **Then** chữ
   vẫn hiển thị bình thường và avatar giữ biểu cảm trung tính, không lỗi.

---

### User Story 3 - Đổi "não" giữa local và cloud (Priority: P3)

Người dùng có thể chuyển sang "não" cloud (Claude) khi muốn nhân vật thông minh hơn, chỉ bằng cách
sửa file cấu hình, không phải sửa code.

**Why this priority**: Hữu ích nhưng không bắt buộc. Mặc định vẫn là local.

**Independent Test**: Đổi cấu hình sang cloud, khởi động lại, kiểm tra trang báo đúng provider và
chat hoạt động (hoặc báo lỗi rõ nếu thiếu key).

**Acceptance Scenarios**:

1. **Given** cấu hình chọn cloud nhưng thiếu key, **When** gửi tin, **Then** trang báo cần điền key.

---

### Edge Cases

- Tag cảm xúc bị cắt đôi giữa hai mảnh stream (`[hap` + `py]`) vẫn được nhận đúng.
- Người dùng gửi tin mới hoặc xóa chat khi câu trả lời đang stream: request cũ bị hủy, lịch sử không lệch.
- Lịch sử rất dài: chỉ gửi các lượt gần nhất, luôn bắt đầu bằng lượt của người dùng.
- Model local trả về lỗi giữa chừng (vd hết VRAM): hiện lỗi, không lưu câu trả lời dở vào lịch sử.
- Chưa có file model 3D: trang hướng dẫn cách thêm, chat vẫn dùng được.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST cho phép chat bằng tiếng Việt với nhân vật có tính cách cố định.
- **FR-002**: Câu trả lời MUST hiển thị dần theo thời gian thực, không chờ trả lời xong.
- **FR-003**: Cấu hình mặc định MUST chạy hoàn toàn trên máy người dùng, không cần mạng hay API key.
- **FR-004**: Hệ thống MUST tách nhãn cảm xúc khỏi câu trả lời: chữ hiển thị không chứa nhãn, còn
  cảm xúc dùng để đổi biểu cảm avatar.
- **FR-005**: Avatar MUST có chuyển động nghỉ (thở, chớp mắt, lắc đầu nhẹ) và nhép miệng khi đang trả lời.
- **FR-006**: Người dùng MUST nạp được model nhân vật bằng cách đặt file vào thư mục quy định hoặc kéo thả.
- **FR-007**: Lịch sử chat MUST được giữ qua lần tải lại trang và xóa được bằng một nút.
- **FR-008**: Mọi lỗi (chưa bật "não", chưa tải model, thiếu key, lỗi giữa chừng) MUST hiện thành câu
  tiếng Việt dễ hiểu.
- **FR-009**: Người dùng MUST đổi được giữa "não" local và cloud chỉ bằng cấu hình.

### Key Entities

- **Lượt chat**: vai (người dùng / nhân vật) và nội dung. Lượt của nhân vật lưu bản gốc còn nhãn cảm xúc.
- **Cảm xúc**: một trong 6 giá trị: neutral, happy, angry, sad, relaxed, surprised.
- **Nhân vật (persona)**: tên, giọng điệu, cách xưng hô, quy ước nhãn cảm xúc.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Khi model đã nạp sẵn, chữ đầu tiên hiện trong ≤ 2 giây ở ít nhất 4/5 lần thử.
- **SC-002**: Ở ít nhất 4/5 câu trả lời thử, nhân vật trả lời bằng tiếng Việt tự nhiên và có ít nhất
  một nhãn cảm xúc hợp lệ.
- **SC-003**: Không lần thử nào để lộ nhãn cảm xúc thô trong khung chat.
- **SC-004**: Toàn bộ test tự động chạy được không cần mạng, GPU hay key, và đều pass.
- **SC-005**: Khi "não" chưa sẵn sàng, 100% lần gửi tin hiện thông báo lỗi có hướng khắc phục.

## Assumptions

- Máy người dùng: Windows 11, GPU RTX 5070 8GB VRAM. Model local cỡ 7–9B (nén 4-bit) vừa VRAM.
- Model 3D định dạng VRM, do người dùng tự tạo (VRoid Studio) hoặc tải hợp lệ.
- Chưa có giọng nói (TTS/STT) trong tính năng này; đó là tính năng sau.
- Trí nhớ chỉ là các lượt chat gần nhất; trí nhớ dài hạn là tính năng sau.
