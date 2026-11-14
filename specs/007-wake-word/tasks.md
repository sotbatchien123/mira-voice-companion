# Tasks: 007-wake-word

Plan ngắn: nhận diện ở server (cùng chỗ với STT, dễ test bằng chuỗi đã đo), frontend chỉ quyết định *khi nào* cần tên.

- [x] T001 Đo Zipformer với câu gọi tên / câu dễ nhầm (3 giọng VieNeu)
- [x] T002 `app/wake.py` + `tests/test_wake.py` (chuỗi đo được)
- [x] T003 `/api/stt` trả `wake`, sửa tên; health trả `wake`; `.env.example`
- [x] T004 Frontend: cửa sổ trò chuyện, bỏ qua câu không gọi tên, gợi ý trên ô nhập, không đổi tư thế khi đang chờ tên
- [x] T005 Kiểm chứng với mic giả lập
  — Im 60s: câu TV bị bỏ qua (STT ra đúng chữ, wake=false), ô nhập gợi ý gọi tên. "Mira ơi…" → trả lời sau 3,5s.
  Nói tiếp không tên ngay sau đó → trả lời. Lỗi bắt được: lời chào treo 94s làm câu TV lọt → bỏ luật "đang trả lời".
- [x] T006 README, GHI_NHO, commit
