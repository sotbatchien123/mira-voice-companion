# Tasks: 004-long-term-memory

## Phase 1: Foundational

- [x] T001 `ChatLLM`: `stream(history, system)`, `complete(messages, json_mode)` cho Ollama và Claude; cập nhật fake trong test
- [x] T002 `app/memory.py`: `Fact`, `MemoryStore` (luật theo loại, trùng, tối đa 60, ghi nguyên tử, file hỏng → rỗng)
- [x] T003 `app/memory.py`: prompt trích xuất, `parse_facts`, `render_memory` (giới hạn ký tự), `system_prompt(now, facts)`
- [x] T004 `.gitignore` thêm `data/`; `.env(.example)`: `MEMORY_ENABLED`

## Phase 2: US1 - Nhớ qua nhiều phiên (P1)

- [x] T005 `app/main.py`: system prompt có ngày giờ + trí nhớ; trích xuất song song với giọng sau `text_done`; log `kind: memory`
- [x] T006 [US1] Test: store, parser, render, system prompt, trích xuất sau lượt chat, lỗi trích xuất không hỏng chat
- [x] T007 [US1] Kiểm chứng thật: kể 3 điều → xóa chat → hỏi lại; chuyển nhà; câu chào không sinh điều nhớ
  — `scripts/verify_memory.py` với qwen3:8b: phiên mới nhớ đúng 3/3 (Khoa, lập trình, Mướp); chuyển nhà → còn 1 điều nơi ở (Sài Gòn);
  4 câu chào/hỏi → 0 điều mới; chữ đầu 0,14–0,29s; lịch sử 41 lượt dài → giữ 19, prompt thật 2465 token (≤ 3584).

## Phase 3: US2 - Xem/xóa (P2)

- [x] T008 `GET /api/memory`, `DELETE /api/memory/{id}`, `DELETE /api/memory` + test
- [x] T009 Frontend: nút "Trí nhớ", `<dialog>` danh sách, Quên / Quên hết; kiểm chứng trên trình duyệt

## Phase 4: US3 - Không cắt ngầm (P3)

- [x] T010 `trim_history` theo ngân sách ký tự + test; đo `prompt_eval_count` thật với lịch sử dài

## Phase 5: Polish

- [x] T011 README, GHI_NHO; `uv run pytest`; commit
- [x] T012 Header `Cache-Control: no-cache` cho file giao diện (phát hiện khi kiểm chứng: trình duyệt dùng main.js cũ sau khi cập nhật)
