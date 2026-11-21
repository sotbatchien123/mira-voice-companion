# AGENTS.md — Luật làm việc cho mọi AI agent trong dự án Mira

File này dành cho mọi agent làm việc trong repo (Claude Code, Antigravity, Codex…).
Yêu cầu mới nhất của người dùng luôn được ưu tiên hơn file này.

## Bắt đầu mỗi phiên

1. Đọc [`GHI_NHO.md`](GHI_NHO.md) trước khi sửa gì. Đây là nguồn sự thật về trạng thái dự án. Nếu nó khác README thì tin GHI_NHO, nhưng vẫn kiểm tra file thực tế.
2. Chạy `git status` và `git branch --show-current`. Không đụng vào thay đổi chưa commit hay file untracked của người khác.

## Giao tiếp

- Trả lời bằng **tiếng Việt**, giọng thân mật: xưng "mình", gọi "bạn", câu ngắn.
- Báo đúng những gì đã kiểm chứng và những gì chưa. Không nói "đã pass", "đã xong" khi chưa có bằng chứng.

## Dự án trong một đoạn

Mira là bạn trò chuyện 3D nói tiếng Việt, chạy hoàn toàn trên máy:
- **Backend:** Python 3.12 + FastAPI, quản lý bằng `uv`, code trong `app/`.
- **Frontend:** JS thuần + importmap, Three.js + three-vrm, code trong `web/`. Thư viện vendor nằm ở `web/vendor/`, không dùng Node.
- **Model chạy local:** LLM Ollama `qwen3:8b`, TTS VieNeu-TTS (giọng Mỹ Duyên), STT Zipformer (sherpa-onnx).
- **Máy dev:** RTX 5070 Laptop **8GB VRAM**, khi LLM đã nạp thì gần như hết VRAM. Không thêm model chạy GPU nếu chưa đo và chưa hỏi người dùng.

## Lệnh

```bash
uv sync                                    # cài
uv run pytest -q                           # test (phải xanh hết trước khi báo xong)
uv run uvicorn app.main:app --reload       # chạy server, mở http://localhost:8000
```

Sửa `.env` thì phải khởi động lại server, vì `--reload` không theo dõi `.env`.

## Quy trình

- **Tính năng mới hoặc đổi hành vi:** làm theo Spec Kit, mỗi tính năng một thư mục `specs/NNN-ten/` (spec, plan, tasks). Xem `specs/007…009` làm mẫu.
- **Sửa lỗi:** viết test tái hiện lỗi, thấy đỏ rồi mới sửa. Frontend chưa có test JS, nên tái hiện lỗi trong trình duyệt và giả lập `/api/*` thay vì đụng dữ liệu thật.
- **Không xóa test, không nới assertion** để cho xanh. Chỉ đổi kỳ vọng khi hợp đồng hành vi thật sự đổi, và phải ghi lý do.
- Giữ thay đổi đúng phạm vi yêu cầu. Không format toàn repo, không nâng dependency hàng loạt.

## Git

- **Chỉ commit hoặc push khi người dùng yêu cầu.** Làm trên nhánh riêng, không commit thẳng vào `main`.
- Commit message viết tiếng Việt, mỗi tính năng một commit.
- **Không bao giờ commit:** `.env`, `data/` (trí nhớ cá nhân của Mira), `logs/`, `models/`, `web/models/*.vrm`, `CV_Projects_AIML.md` (CV riêng của người dùng), `.obsidian/`.
- Repo đang **public** trên GitHub. Không đưa token, mật khẩu, email thật, đường dẫn riêng của máy (`C:\Users\...`) vào code, log hay tài liệu.

## Khi nhiều agent cùng làm

Người dùng có thể giao việc song song cho nhiều agent (ví dụ Claude Code và Antigravity):
- **Mỗi agent một nhánh.** Trước khi bắt đầu, ghi vào "Việc tiếp theo" trong GHI_NHO: ai đang làm gì, trên nhánh nào.
- **Chia theo ranh giới file:** `app/` + `tests/` (Python) và `web/` (frontend) là hai vùng tách biệt. Hai agent không sửa cùng một file cùng lúc.
- `GHI_NHO.md` chỉ ghi ở **cuối việc**, sau khi kéo bản mới nhất, để giảm xung đột khi gộp.

## Cuối phiên

Nếu có thay đổi hoặc phát hiện đáng kể, cập nhật `GHI_NHO.md`:
- Thêm một mục mới lên **đầu** "Nhật ký phiên": ngày, việc đã làm, file đã đổi, việc còn dở.
- Sửa "Trạng thái hiện tại" và "Việc tiếp theo" cho đúng thực tế.
- Không xóa mục nhật ký cũ. Nếu mục cũ sai thì thêm ghi chú sửa lại.
