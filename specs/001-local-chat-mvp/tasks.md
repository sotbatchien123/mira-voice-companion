# Tasks: Chat với nhân vật 3D bằng "não" chạy local

**Input**: Design documents from `specs/001-local-chat-mvp/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Có. Constitution IV yêu cầu test offline cho mọi logic mới.

**Ghi chú**: Các task đã `[x]` được làm trước khi áp dụng Spec Kit (phiên 2026-11-13). Task còn mở là
phần kiểm chứng với Ollama thật và model VRM thật.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Tạo môi trường Python 3.12 bằng uv, khai báo dependency trong `pyproject.toml`
- [x] T002 [P] Vendor three.js 0.187 + three-vrm 3.5.5 vào `web/vendor/` kèm `VERSIONS.txt` và LICENSE
- [x] T003 [P] Tạo `.env.example`, `.gitignore` (`.env`, `.venv`, `web/models/*.vrm`)
- [x] T004 Cài Ollama bản chính thức và tải model `qwen3:8b` (research R1) — qwen3:8b v0.40.16, 5.2GB, Q4_K_M, test warmup 0.5s

## Phase 2: Foundational

- [x] T005 Hợp đồng `ChatLLM` + `make_llm()` trong `app/llm.py` (contracts/chat-llm.md)
- [x] T006 [P] Parser tag cảm xúc stream-safe trong `app/emotion_tags.py`
- [x] T007 [P] Test parser trong `tests/test_emotion_tags.py`
- [x] T008 FastAPI app: validate `ChatTurn`, cắt lịch sử, SSE `/api/chat`, `/api/health`, phục vụ `web/` trong `app/main.py`

## Phase 3: User Story 1 - Trò chuyện không cần API (P1) 🎯 MVP

**Goal**: Chat tiếng Việt, stream chữ, chạy hoàn toàn local.

**Independent Test**: quickstart.md, các dòng SC-001, SC-002, SC-003, SC-005.

- [x] T009 [P] [US1] Test API với LLM giả (stream, refusal, lỗi giữa chừng, 422, cắt lịch sử) trong `tests/test_api.py`
- [x] T010 [P] [US1] Test `OllamaLLM` bằng `httpx.MockTransport` trong `tests/test_ollama.py`
- [x] T011 [US1] `OllamaLLM` gọi `/api/chat` NDJSON, `keep_alive`, `think`, lỗi tiếng Việt trong `app/llm.py`
- [x] T012 [US1] Persona tiếng Việt + quy ước tag trong `app/persona.py`
- [x] T013 [US1] Giao diện chat, localStorage, hủy request, nút xóa trong `web/main.js`, `web/chat_client.js`
- [x] T014 [US1] Kiểm chứng thật: `/api/health` báo ollama + model đúng ✅ provider="ollama", model="qwen3:8b"
- [x] T015 [US1] Kiểm chứng thật: đo thời gian tới chữ đầu tiên cho 5 câu (SC-001) ✅ 5/5 câu ≤ 2s (warmup 0.5s)
- [x] T016 [US1] Kiểm chứng thật: kiểm tra tiếng Việt + tỷ lệ có tag cảm xúc + không lộ tag (SC-002, SC-003) 5/5 câu có tag, 0 lộ tag, không còn dấu cách đôi; xưng hô sai 1/24 câu (sau khi sửa persona)
- [x] T017 [US1] Kiểm chứng thật: model chưa pull → hiện lệnh `ollama pull` (SC-005) (Ollama thật, model `khong-co-model:1b` → "Chạy: ollama pull khong-co-model:1b")
- [x] T018 [US1] Kiểm chứng thật trên trình duyệt: gửi tin, xem chữ hiện dần, tải lại trang vẫn còn lịch sử ✅ stream + localStorage ok

## Phase 4: User Story 2 - Biểu cảm trên mặt (P2)

**Goal**: Avatar đổi biểu cảm theo tag, nhép miệng khi nói.

**Independent Test**: quickstart.md, dòng US2 (cần file VRM).

- [x] T019 [US2] `web/avatar.js`: nạp VRM, idle, biểu cảm, chớp mắt, khẩu hình giả lập
- [x] T020 [US2] Kiểm chứng với model VRM thật: tay buông tự nhiên (`relaxArms`), mặt đổi biểu cảm (cần người dùng cung cấp `.vrm`)
  — `Mira.vrm` (VRoid, VRM 1.0, 54 xương, đủ expression): tay buông dọc người với ±1,2 rad; ghi `setValue` thật: `sad` 0,8 khi câu buồn,
  `surprised` khi câu ngạc nhiên, `blink` 1,0. Phát hiện và sửa tag lạ `[concerned]` lộ ra khung chat.

## Phase 5: User Story 3 - Đổi não local/cloud (P3)

- [x] T021 [US3] `ClaudeLLM` với streaming + server-side fallback trong `app/llm.py`
- [x] T022 [US3] Test chọn provider và thiếu key trong `tests/test_ollama.py`, `tests/test_api.py`

## Phase 6: Polish

- [x] T023 Cập nhật `README.md`, `GHI_NHO.md` với kết quả kiểm chứng thật và model đã chọn
- [x] T024 Chạy lại `uv run pytest` sau mọi chỉnh sửa 24/24 pass

## Dependencies & Execution Order

- T004 chặn T014–T018.
- T020 chặn bởi việc người dùng cung cấp file `.vrm`; không chặn US1.
- T023, T024 chạy sau cùng.

## Implementation Strategy

MVP = Phase 1–3. Hoàn thành T004, T014–T018 là đủ để coi US1 đạt. US2 cần thêm T020.
