# Tasks: 006-proactive-mira

Plan ngắn: `app/presence.py` lưu lần nói cuối/lần chào cuối và mô tả khoảng vắng; luồng trả lời trong `app/main.py` tách
thành hàm dùng chung cho `/api/chat` và `/api/proactive` (chỉ lượt của người dùng mới trích trí nhớ);
`trim_history` gộp lượt liền nhau cùng vai và chèn lượt mở đầu khi lịch sử bắt đầu bằng Mira; frontend tách luồng
"chờ Mira trả lời" thành hàm dùng chung cho gửi tin, chào và hỏi thăm.

- [x] T001 Spike prompt (`spikes/proactive_prompt.py`); `today_line` có buổi, điều nhớ có "N ngày trước"
- [x] T002 `app/presence.py` + test
- [x] T003 `trim_history`: gộp lượt cùng vai, lịch sử bắt đầu bằng Mira + test
- [x] T004 `POST /api/proactive`, cập nhật lần nói cuối trong `/api/chat`, health thêm `proactive` + test
- [x] T005 Frontend: chào khi mở trang, hỏi thăm khi im lâu, tách hàm chờ trả lời
- [x] T006 Kiểm chứng thật: chào sau vắng / không chào khi tải lại / hỏi thăm 1 lần
  — Mở trang sau 2 ngày vắng: tự chào, chữ đầu 0,44s (chỉ chữ vì trình duyệt chưa cho phát âm thanh). Tải lại: không chào.
  Im 1 phút (cấu hình thử): đúng 1 lần hỏi thăm ("Anh đi phỏng vấn xong chưa?..."), 113s sau vẫn 1.
  Lỗi bắt được: (1) model hỏi "hôm nay anh đi phỏng vấn à?" cho sự kiện "ngày mai" nói 2 ngày trước → code đổi mốc tương đối
  thành ngày + nhãn đã diễn ra/hôm nay/sắp tới; mẫu lại 4 lần: không còn "sắp" sai. (2) hỏi thăm 2 lần vì Mira nói xong
  lại bật cờ hỏi thăm → chỉ hoạt động của người dùng mới bật lại.
  Còn: model 8B đôi khi tự thêm chi tiết nhỏ ("Mướp tập trung vào bát cơm mới") dù prompt cấm.
- [x] T007 README, GHI_NHO, commit
- [x] T008 `resolve_relative_dates` + `event_status` trong `app/memory.py` (áp dụng cho mọi lượt chat, không riêng lời chủ động)
