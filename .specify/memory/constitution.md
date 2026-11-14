<!--
Sync Impact Report
- Version change: 1.0.0 → 1.0.1 (PATCH: đổi tên dự án thành "Mira – 3D Vietnamese Voice Companion", không đổi nguyên tắc)
- Trước đó: (template) → 1.0.0
- Principles added: I. Bộ não thay thế được; II. Độ trễ hội thoại là ưu tiên; III. Local-first & riêng tư;
  IV. Test không phụ thuộc dịch vụ thật; V. Đơn giản, không build step
- Sections added: Ràng buộc kỹ thuật; Quy trình phát triển; Governance
- Removed sections: none
- Deferred TODOs: none
-->

# Mira – 3D Vietnamese Voice Companion Constitution

## Core Principles

### I. Bộ não thay thế được

Mọi LLM MUST đi qua hợp đồng `ChatLLM.stream()` trong `app/llm.py`: phát `("text", delta)` rồi đúng
một `("stop", stop_reason)` với stop_reason đã chuẩn hóa (`end_turn`, `max_tokens`, `refusal`).
Server, frontend và phần xử lý cảm xúc MUST NOT rẽ nhánh theo tên provider. Thêm hoặc đổi provider
chỉ được chạm `app/llm.py`, cấu hình `.env` và test.

Lý do: dự án sẽ đổi qua lại giữa model local và cloud, và sau này sang Hướng 4. Một hợp đồng chung
giữ chi phí đổi ở mức một file.

### II. Độ trễ hội thoại là ưu tiên

Câu trả lời MUST được stream từ đầu đến cuối (LLM → SSE → giao diện, sau này → TTS), không chờ
xong cả câu. Mục tiêu: chữ đầu tiên hiện dưới 2 giây khi model đã nạp sẵn trong GPU. Tính năng nào
làm tăng độ trễ MUST nêu rõ con số đánh đổi trong plan.

Lý do: cảm giác "đang nói chuyện thật" phụ thuộc vào độ trễ nhiều hơn độ thông minh của model.

### III. Local-first & riêng tư

Cấu hình mặc định MUST chạy được hoàn toàn trên máy người dùng (Ollama), không cần API key hay mạng.
Bí mật (API key, token), file `.env` và model VRM có license riêng MUST NOT vào git hay log. Dữ liệu
hội thoại MUST NOT gửi tới dịch vụ ngoài, trừ provider mà người dùng tự chọn trong `.env`.

Lý do: đây là bạn đồng hành cá nhân. Người dùng kiểm soát dữ liệu và chi phí của mình.

### IV. Test không phụ thuộc dịch vụ thật

Logic mới hoặc lỗi đã sửa MUST có test chạy được bằng `uv run pytest` mà không cần Ollama, GPU,
mạng hay API key. Dịch vụ ngoài được thay bằng fake (`dependency_overrides`, `httpx.MockTransport`).
Kiểm thử với model thật là bước riêng, MUST được ghi rõ là đã chạy hay chưa. MUST NOT xóa test hay
nới assertion chỉ để pass.

Lý do: test chạy nhanh và miễn phí thì sẽ được chạy thường xuyên. Tách bạch "test pass" với
"đã chạy thật" giúp báo cáo trung thực.

### V. Đơn giản, không build step

Backend là Python 3.12 do uv quản lý. Frontend là JavaScript thuần với importmap; thư viện được
vendor trong `web/vendor/` kèm phiên bản và license. MUST NOT thêm Node, bundler hay framework
frontend khi chưa có nhu cầu cụ thể được ghi trong plan. Dependency mới MUST có lý do rõ ràng.

Lý do: một runtime duy nhất giúp dễ cài, dễ sửa, và hợp với các thư viện AI (TTS, STT) chạy bằng Python.

## Ràng buộc kỹ thuật

- Phần cứng mục tiêu: laptop RTX 5070 8GB VRAM. LLM, TTS và STT chạy local MUST cùng vừa ngân sách
  VRAM này. Plan của tính năng dùng GPU MUST ghi ước tính VRAM.
- Giao thức SSE `/api/chat` (`emotion`, `text`, `done{raw}`, `error`) là hợp đồng giữa server và
  frontend. Đổi giao thức MUST cập nhật cả hai phía, README và test trong cùng một thay đổi.
- Ngôn ngữ trò chuyện mặc định là tiếng Việt. Tag cảm xúc chỉ gồm 6 expression chuẩn VRM.
- Lỗi MUST hiện cho người dùng thành câu tiếng Việt dễ hiểu. MUST NOT nuốt lỗi hay giả vờ thành công.

## Quy trình phát triển

- Đầu phiên đọc `GHI_NHO.md`. Cuối phiên có thay đổi thì cập nhật trạng thái, việc tiếp theo và nhật ký.
- Tính năng lớn hoặc kéo dài nhiều phiên đi theo Spec Kit: specify → plan → tasks → implement.
  Sửa nhỏ thì làm trực tiếp.
- Trước khi bàn giao: chạy `uv run pytest`, thử trên trình duyệt nếu đổi giao diện, và báo rõ phần
  nào chưa kiểm chứng.

## Governance

Constitution này đứng trên các quy ước khác của dự án. Sửa đổi phải ghi trong Sync Impact Report và
tăng phiên bản theo semver: MAJOR khi bỏ hoặc định nghĩa lại nguyên tắc, MINOR khi thêm nguyên tắc
hoặc mục, PATCH khi chỉ sửa câu chữ. Mỗi plan MUST có mục "Constitution Check"; vi phạm phải được
ghi lý do trong bảng Complexity Tracking hoặc sửa trước khi implement.

**Version**: 1.0.1 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-14
