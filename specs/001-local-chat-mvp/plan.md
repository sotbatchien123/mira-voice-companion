# Implementation Plan: Chat với nhân vật 3D bằng "não" chạy local

**Branch**: `001-local-chat-mvp` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-local-chat-mvp/spec.md`

## Summary

Web app một trang: avatar VRM render bằng three.js, khung chat bên cạnh. Backend FastAPI nhận lịch sử
chat, gọi "não" (mặc định Ollama local, tùy chọn Claude API), tách tag cảm xúc khỏi luồng text rồi
stream về trình duyệt bằng SSE. Phần lớn đã được xây trước khi áp dụng Spec Kit; plan này ghi lại
thiết kế và bổ sung bước kiểm chứng với Ollama thật.

## Technical Context

**Language/Version**: Python 3.12.16 (uv), JavaScript ES2022 chạy trực tiếp trên trình duyệt

**Primary Dependencies**: FastAPI, uvicorn, httpx (gọi Ollama), anthropic 2.x (Claude), python-dotenv;
frontend: three.js 0.187 + @pixiv/three-vrm 3.5.5 (vendor)

**Storage**: Lịch sử chat trong localStorage của trình duyệt; không có database

**Testing**: pytest + FastAPI TestClient; fake LLM qua `dependency_overrides`, Ollama giả qua `httpx.MockTransport`

**Target Platform**: Windows 11, trình duyệt Chromium, GPU RTX 5070 Laptop 8GB

**Project Type**: Web application (backend Python + frontend tĩnh, một server)

**Performance Goals**: Chữ đầu tiên ≤ 2 giây khi model đã nạp; render avatar mượt ở 60 fps

**Constraints**: Model local + KV cache ≤ ~6GB VRAM để chừa chỗ cho TTS/STT sau này; không build step

**Scale/Scope**: Một người dùng, chạy local

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Nguyên tắc | Đánh giá |
|---|---|
| I. Bộ não thay thế được | PASS: `ClaudeLLM` và `OllamaLLM` cùng hợp đồng `stream()`, chọn bằng `LLM_PROVIDER` |
| II. Độ trễ là ưu tiên | PASS: stream LLM → SSE → DOM; `keep_alive=30m`, `think=false`. SC-001 cần đo thật (T020) |
| III. Local-first & riêng tư | PASS: mặc định Ollama; `.env` và `*.vrm` trong `.gitignore` |
| IV. Test không phụ thuộc dịch vụ thật | PASS: 20 test chạy offline; kiểm chứng thật là task riêng |
| V. Đơn giản, không build step | PASS: Python + JS thuần, thư viện vendor kèm license |

Đánh giá lại sau Phase 1: không đổi, không có vi phạm.

## Project Structure

### Documentation (this feature)

```text
specs/001-local-chat-mvp/
├── plan.md              # File này
├── research.md          # Phase 0: các quyết định kỹ thuật
├── data-model.md        # Phase 1: thực thể và quy tắc
├── quickstart.md        # Phase 1: cách chạy và kiểm chứng
├── contracts/
│   ├── chat-sse.md      # Giao thức POST /api/chat
│   └── chat-llm.md      # Hợp đồng ChatLLM.stream()
├── checklists/requirements.md
└── tasks.md             # Phase 2
```

### Source Code (repository root)

```text
app/
├── main.py           # FastAPI: /api/chat (SSE), /api/health, phục vụ web/
├── llm.py            # ChatLLM, ClaudeLLM, OllamaLLM, make_llm
├── persona.py        # System prompt nhân vật
└── emotion_tags.py   # Parser tag cảm xúc (stream-safe)
web/
├── index.html        # importmap trỏ tới vendor/
├── main.js           # UI chat, localStorage
├── chat_client.js    # Đọc SSE
├── avatar.js         # three.js + VRM: idle, biểu cảm, khẩu hình
├── style.css
├── models/           # waifu.vrm do người dùng đặt vào (gitignored)
└── vendor/           # three.js, three-vrm
tests/
├── test_emotion_tags.py
├── test_api.py
└── test_ollama.py
```

**Structure Decision**: Một server FastAPI vừa phục vụ API vừa phục vụ file tĩnh, nên không cần
proxy hay CORS, và chỉ có một lệnh chạy.

## Complexity Tracking

Không có vi phạm constitution cần giải trình.
