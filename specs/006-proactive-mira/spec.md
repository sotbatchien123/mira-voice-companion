# Feature Specification: Mira chủ động (chào khi mở, hỏi thăm khi im lâu)

**Feature Branch**: `006-proactive-mira`

**Created**: 2026-11-14

**Status**: Implemented

**Input**: Người dùng chọn "Mira chủ động": cảm giác bạn đồng hành thật thay vì chỉ trả lời khi được hỏi.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chào khi mở trang (Priority: P1)

Người dùng mở trang sau một thời gian vắng. Mira tự chào một câu ngắn hợp giờ trong ngày, có thể hỏi thăm một
chuyện trong trí nhớ ("Anh đi phỏng vấn FPT rồi à?").

**Acceptance Scenarios**:

1. **Given** lần nói chuyện cuối cách ≥ 30 phút (hoặc chưa từng), **When** mở trang, **Then** Mira tự chào.
2. **Given** vừa nói chuyện < 30 phút hoặc vừa chào xong, **When** tải lại trang, **Then** không chào lại.
3. Lời chào được lưu vào lịch sử như một lượt của Mira, để lượt sau model biết mình đã hỏi gì.
4. Trình duyệt chưa cho phát âm thanh (chưa có cú bấm nào): chào bằng chữ + miệng giả lập; có giọng khi đã cho phép.

### User Story 2 - Hỏi thăm khi im lâu (Priority: P2)

Trang đang mở, người dùng im ≥ N phút (mặc định 10). Mira hỏi thăm MỘT lần cho đến khi người dùng nói tiếp.

**Acceptance Scenarios**:

1. Không hỏi khi: đang gõ dở, đang giữ mic/đang nói, Mira đang nói/đang trả lời, tab đang ẩn.
2. Không chào lại, không trách móc; chỉ nhắc điều có trong cuộc trò chuyện/trí nhớ.
3. Tắt được bằng cấu hình (`PROACTIVE_CHECKIN_MINUTES=0`).

### Edge Cases

- Lịch sử bắt đầu bằng lượt của Mira (lời chào) hoặc có 2 lượt Mira liền nhau (chào rồi hỏi thăm): vẫn gửi đúng
  luân phiên user/assistant cho mọi provider (Claude bắt buộc).
- Lời nhắc hệ thống cho lời chào không được hiện ra, không lưu lịch sử, không bị trích làm "điều đáng nhớ".
- "Não" chưa sẵn sàng: không chào, không báo lỗi thêm (đã có báo lỗi từ health).

## Requirements *(mandatory)*

- **FR-001**: Server lưu thời điểm người dùng nói lần cuối và lần chào cuối (`data/presence.json`).
- **FR-002**: `POST /api/proactive {kind: greet|checkin, messages, voice}` trả SSE như `/api/chat`, hoặc `204` nếu
  chưa đến lúc (chào gần đây, chưa im đủ lâu, tính năng tắt).
- **FR-003**: Lời nhắc cho model nêu khoảng thời gian vắng ("khoảng 1 ngày"), giờ trong ngày có buổi, và cấm lộ ghi chú.
- **FR-004**: Dòng ngày giờ ghi rõ buổi; mỗi điều nhớ ghi "nói cách đây N ngày" (spike: thiếu thì model nói "trưa rồi"
  lúc 15:00 và không biết sự kiện đã qua chưa).
- **FR-005**: Cấu hình: `PROACTIVE_GREETING`, `GREET_MIN_GAP_MINUTES`, `PROACTIVE_CHECKIN_MINUTES`.

## Success Criteria *(mandatory)*

- **SC-001**: Mở trang sau ≥ 30 phút: có lời chào trong ≤ 6s (gồm nạp model); tải lại ngay: không chào lần 2.
- **SC-002**: Lời chào đúng buổi và, khi có trí nhớ phù hợp, hỏi thăm đúng một chuyện có thật trong trí nhớ (đọc bằng mắt 3 lần).
- **SC-003**: Im đủ lâu: đúng 1 lần hỏi thăm; người dùng nói tiếp thì bộ đếm lại từ đầu.
- **SC-004**: Test offline pass.
