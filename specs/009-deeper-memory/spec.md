# Feature Specification: Trí nhớ sâu hơn (tóm tắt buổi trò chuyện, bỏ sự kiện cũ)

**Feature Branch**: `009-deeper-memory`

**Created**: 2026-11-14

**Status**: Implemented

**Input**: Người dùng: "làm 2 cái này đi" (giọng theo cảm xúc + trí nhớ sâu hơn).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nhớ hôm trước nói chuyện gì (Priority: P1)

Hôm qua anh kể mèo Mướp ốm, mai đưa đi thú y. Hôm nay mở trang, Mira hỏi "Mướp đi khám sao rồi anh?" dù lịch sử chat
đã bị xóa hay bị cắt.

**Acceptance Scenarios**:

1. Im quá 30 phút: buổi vừa rồi được tóm tắt 1–3 câu (data/episodes.json). Server chạy liên tục thì tóm tắt ngay
   khi hết 30 phút; server tắt giữa chừng thì tóm tắt ở lượt kế tiếp (lời chào chờ tóm tắt xong rồi mới chào).
2. System prompt có tối đa 3 buổi gần nhất, kèm "hôm qua / N ngày trước", mốc tương đối đổi thành ngày + nhãn.
3. Buổi chỉ có chào hỏi (< 30 ký tự của anh) không gọi model.
4. Nút "Trí nhớ" hiện các buổi đã tóm tắt, xóa được từng buổi; "Quên hết" xóa cả tóm tắt.

### User Story 2 - Bỏ sự kiện đã qua lâu (Priority: P2)

"Thứ Sáu này anh đi phỏng vấn" sau 2 tuần không còn nằm trong trí nhớ. Code bỏ (không nhờ model): loại `su_kien`, có
ngày cụ thể, mọi ngày đã qua quá 14 ngày.

### Edge Cases

- Lượt mới đến khi model đang tóm tắt: không mất, không tóm tắt chồng.
- Ngày không tồn tại ("31/02") không làm hỏng lượt chat.
- Lời nhắc ẩn của lời chào/hỏi thăm không bị ghi vào buổi trò chuyện.

## Đo trước (spike `spikes/episode_summary.py`, qwen3:8b, 3 buổi × 3 lần)

Tóm tắt trung thực, ~1,5s. Bản prompt đầu bỏ "FPT" và viết tắt "khám mai"/"vào thứ Sáu" (code không đổi được ra ngày)
→ thêm luật giữ tên riêng, viết đủ mốc thời gian; đo lại: 9/9 giữ tên, "thứ Sáu này"/"ngày mai" đúng dạng.

## Requirements *(mandatory)*

- **FR-001**: `app/episodes.py`: `EpisodeStore` (record, due, close, close_later, delete, clear), `render_episodes`.
- **FR-002**: `/api/chat` ghi lượt anh + lời Mira (bỏ tag); hẹn tóm tắt sau khoảng im. `/api/proactive` ghi lời Mira.
- **FR-003**: `MemoryStore.expire_events(today)` chạy trước khi dựng system prompt.
- **FR-004**: `GET /api/memory` trả thêm `episodes`; `DELETE /api/memory/episodes/{id}`.
- **FR-005**: `EPISODE_GAP_MINUTES` (30). Không ghi nội dung vào log, chỉ số lượt/thành công.

## Success Criteria *(mandatory)*

- **SC-001**: Test offline pass.
- **SC-002**: Chạy thật với qwen3:8b: nói chuyện, giả lập vắng 1 ngày, mở trang → lời chào nhắc đúng chuyện buổi trước.
