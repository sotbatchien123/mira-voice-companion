# Tasks: 005-lively-avatar

Plan ngắn: logic thuần ở `web/lipsync.js` (nguyên âm từng âm tiết, bắt nhịp âm tiết từ âm lượng); `web/avatar.js` trộn
5 khẩu hình theo âm tiết hiện tại × độ mở, thêm lớp cử động đầu (gật theo nhịp, dáng theo cảm xúc, lắng nghe);
`web/main.js` đưa chữ đoạn đang đọc và trạng thái mic vào avatar. Không có test JS tự động (không dùng Node — constitution V):
kiểm chứng bằng script chạy trong trình duyệt trên VRM thật. Bản `?debug=1` để lộ avatar ra `window` cho việc đo.

- [x] T001 `web/lipsync.js`: `syllableVisemes(text)`, `SyllableTracker` (bắt nhịp từ âm lượng)
- [x] T002 `web/avatar.js`: 5 khẩu hình, gật theo nhịp, dáng theo cảm xúc, `setListening()`, hook `?debug=1`
- [x] T003 `web/main.js`: `onSegmentStart` đưa chữ vào lipsync; mic bắt đầu/kết thúc nói → lắng nghe
- [x] T004 Kiểm chứng: nguyên âm cho câu mẫu đúng; tỉ lệ nhịp/âm tiết trên giọng thật (SC-001); khẩu hình dùng (SC-002); góc đầu (SC-003)
  — Nguyên âm chính: 24/24 từ mẫu đúng (sau khi thêm luật iê/yê: lần đầu "yêu" ra y).
  Giọng Mỹ Duyên trên Mira.vrm: nhịp/âm tiết 0,73–1,0 ở 5/5 đoạn; dùng đủ 5 khẩu hình (max ~0,6); im lặng → 0.
  Góc đầu (rad) vui x-0,018 z+0,042, buồn x+0,071, ngạc nhiên x-0,047, giận x+0,035, lắng nghe z+0,059, thôi nghe → 0;
  ảnh chụp: buồn cúi, ngạc nhiên ngửa. Không lỗi console.
  Bẫy khi đo: khung trình duyệt bị ẩn thì requestAnimationFrame dừng (elapsed = 0) → phải hiện khung mới đo được.
- [x] T005 README, GHI_NHO, commit
