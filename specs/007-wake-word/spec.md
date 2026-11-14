# Feature Specification: Từ đánh thức "Mira ơi" cho chế độ Rảnh tay

**Feature Branch**: `007-wake-word`

**Created**: 2026-11-14

**Status**: Implemented

**Input**: Người dùng: "Thêm luôn" (từ đánh thức "Mira ơi" cho Rảnh tay, để TV / người khác nói không làm Mira trả lời).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gọi tên khi đã yên lặng (Priority: P1)

Rảnh tay đang bật, đã im một lúc. Trong phòng có TV hay người khác nói: Mira không trả lời. Người dùng nói
"Mira ơi, hôm nay trời đẹp quá": Mira trả lời như bình thường.

**Acceptance Scenarios**:

1. **Given** đã im > cửa sổ trò chuyện (mặc định 60s), **When** câu nói không mở đầu bằng tên Mira, **Then** bỏ qua,
   không gửi, không đổi tư thế lắng nghe, ô nhập gợi ý gọi "Mira ơi".
2. **Given** như trên, **When** câu mở đầu bằng "Mira ơi / Mira à / Này Mira / Ê Mira", **Then** gửi cả câu (tên
   được viết lại đúng "Mira" dù STT nghe nhầm).

### User Story 2 - Đang trò chuyện thì không cần gọi tên (Priority: P1)

Trong vòng 60s kể từ lượt gần nhất (người dùng gửi, hoặc Mira nói xong / đang nói, kể cả lời chào chủ động), nói
bình thường, không cần gọi tên.

### User Story 3 - Giữ để nói không bị ảnh hưởng (Priority: P1)

Bấm giữ nút mic / phím Space là ý định rõ ràng: luôn gửi, không cần tên.

### Edge Cases

- STT hay nghe nhầm tên (đo Zipformer với 3 giọng VieNeu): "Vera ơi", "Me ra ơi", "Vira à", "Mira a",
  "Này mới ra", "Này mi ra", "Visa ơi", "Mara ơi", "Misa ơi", "Đi ra ơi", "Emmira", "Camera" (cho "Ê Mira").
  → nhận diện mờ: tên chắc chắn (mira, emmira…) chấp nhận luôn; tên dễ nhầm (vera, misa, mi ra…) cần "ơi/à/a"
  phía sau hoặc "này/ê/chào" phía trước; "đi ra" chỉ khi có "ơi".
- Không nhận nhầm: "Chị Mai ơi", "Mai mình đi chợ", "Mía ở chợ", "Đi ra ngoài", "Đi ra à?", tên ở giữa câu.
- Chỉ nói "Mira ơi." (không có nội dung): vẫn gửi, Mira đáp "dạ".

## Requirements *(mandatory)*

- **FR-001**: `app/wake.py`: `detect_wake(text) -> (bool, text_đã_sửa_tên)`, chỉ xét 1–2 từ đầu.
- **FR-002**: `/api/stt` trả thêm `wake: bool`; text luôn được sửa tên khi nhận ra (có lợi cho cả giữ để nói).
- **FR-003**: Cấu hình `HANDSFREE_WAKE_WORD` (mặc định bật), `WAKE_WINDOW_SECONDS` (mặc định 60); health trả `wake`.
- **FR-004**: Frontend chỉ đòi tên khi: rảnh tay, không giữ mic, Mira không đang nói/đang trả lời, quá cửa sổ.

## Success Criteria *(mandatory)*

- **SC-001**: Các câu gọi tên đo được ở trên: ≥ 90% được nhận; các câu phủ định: 0 nhận nhầm (test offline).
- **SC-002**: Mic giả lập trong trình duyệt: câu không gọi tên sau khi im → không có lượt mới; "Mira ơi…" → có trả lời;
  trả lời tiếp trong cửa sổ không cần tên.
