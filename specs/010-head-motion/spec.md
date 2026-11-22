# Spec 010: Chuyển động đầu và ánh mắt khi nói

Việc nhỏ (một file `web/avatar.js`), nên chỉ có spec này, không có plan/tasks riêng.

## Vì sao

Khi Mira nói, đầu chỉ gật đều 0,035 rad mỗi âm tiết và lắc theo hình sin cố định. Mắt luôn nhìn thẳng camera. Nhìn lâu
thấy giống robot. Ý tưởng lấy từ DiffPoseTalk (chuyển động đầu theo giọng nói), nhưng làm bằng quy tắc trong JS: không
tốn GPU, không cần model, chạy với mọi model VRM (chỉ dùng xương `neck`/`head` và `lookAt` có sẵn).

## Hành vi

1. **Đầu theo giọng khi đang nói:** cứ 0,8–2 giây đổi sang một hướng mới nhỏ (quay trái/phải ≤ 0,08 rad, ngẩng/cúi
   ≤ 0,03 rad), chuyển mượt. Hết nói thì về lại dáng theo cảm xúc như trước.
2. **Gật theo độ nhấn:** âm tiết to (so với đỉnh âm lượng gần đây) gật sâu hơn, âm tiết nhỏ gật nhẹ
   (0,015–0,05 rad thay vì cố định 0,035).
3. **Ánh mắt:** lúc rảnh và lúc đang nói, thỉnh thoảng (3–7 giây một lần) liếc đi chỗ khác 0,4–1,2 giây rồi nhìn lại
   camera. Khi đang lắng nghe anh nói thì luôn nhìn anh.

Không đổi: dáng theo cảm xúc, nghiêng đầu khi lắng nghe, thở, chớp mắt, nhép môi.

## Kiểm chứng

Không có test JS. Đo trong trình duyệt với giọng giả (`/api/chat` giả lập gửi audio): góc quay đầu khi nói có thay
đổi trong biên độ trên, về lại dáng cũ khi im; mắt có lúc không nhìn camera, lúc lắng nghe thì luôn nhìn camera.
Người dùng xem bằng mắt xem có tự nhiên không.
