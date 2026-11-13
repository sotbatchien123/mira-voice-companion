# Research: 001-local-chat-mvp

## R1. Model local mặc định

- **Decision**: `qwen3:8b` (bản nén Q4_K_M, khoảng 5.2GB) chạy qua Ollama, `think=false`.
- **Rationale**: Theo thư viện Ollama (xem ngày 2026-11-13), các model có tiếng Việt khá và vừa 8GB
  VRAM là Qwen 3/3.5 và Gemma. `qwen3:8b` cân bằng tốt nhất giữa chất lượng và VRAM: còn khoảng 2.5GB
  cho KV cache và cho TTS/STT sau này. Nó cũng hỗ trợ tắt chế độ suy nghĩ để giảm độ trễ.
- **Alternatives considered**:
  - `qwen3.5:9b` (6.6GB): mới hơn nhưng gần chạm trần 8GB khi tính KV cache, không còn chỗ cho TTS.
  - `qwen3.5:4b` (3.3GB): nhẹ, là phương án dự phòng khi thêm TTS/STT cùng lúc.
  - `gemma4:e4b` (6.6GB), `gemma4:12b` (7.7GB): nặng vì kèm vision/audio, không cần cho chat chữ.
  - Các bản Qwen 3.6/3.8: chỉ có từ 27B trở lên, không vừa GPU.

## R2. Cách gọi Ollama

- **Decision**: Dùng API gốc `POST /api/chat` với `stream: true` (NDJSON), qua httpx.
- **Rationale**: API gốc có `keep_alive` (giữ model trong VRAM) và `think` (tắt suy nghĩ), hai tham số
  quyết định độ trễ. Không cần thêm SDK.
- **Alternatives considered**: Endpoint tương thích OpenAI của Ollama (thiếu `keep_alive`/`think`
  ở cấp request); thư viện `ollama` Python (thêm dependency mà không thêm giá trị).

## R3. Tách tag cảm xúc ở đâu

- **Decision**: Ở server, trong `app/emotion_tags.py`, gửi về event `emotion` và `text` đã sạch.
- **Rationale**: TTS sau này chạy ở server cần text sạch. Frontend đơn giản hơn.
- **Alternatives considered**: Tách ở frontend (cách cũ thời Node), không hợp với TTS phía server.

## R4. Truyền stream về trình duyệt

- **Decision**: SSE qua `fetch` + `ReadableStream` (POST body chứa lịch sử).
- **Rationale**: Một chiều server → client là đủ; `EventSource` không gửi được POST body.
- **Alternatives considered**: WebSocket, để dành cho lúc có âm thanh hai chiều (STT).

## R5. Độ trễ kết nối khi Ollama chưa bật

- **Finding**: Trên Windows, kết nối tới cổng chưa mở mất khoảng 2 giây mới báo lỗi (TCP thử lại),
  kể cả khi dùng `127.0.0.1`. Đây là hành vi của hệ điều hành; chấp nhận được vì chỉ xảy ra khi lỗi.
