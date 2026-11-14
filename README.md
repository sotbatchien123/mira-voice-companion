> **Quy định:** Đọc [GHI_NHO.md](GHI_NHO.md) trước khi làm việc với dự án, và cập nhật nó cuối mỗi phiên.

# Mira – 3D Vietnamese Voice Companion

Chatbot nhân vật anime 3D chạy trên trình duyệt: avatar VRM (Three.js + three-vrm), backend Python
(FastAPI), biểu cảm đổi theo tag cảm xúc mà LLM chèn vào câu trả lời, nói thành tiếng bằng giọng tiếng Việt
chạy CPU (VieNeu-TTS, giọng Mỹ Duyên) và nhép miệng theo âm lượng giọng. Nói chuyện được bằng mic
(Zipformer-30M tiếng Việt chạy CPU): giữ để nói, hoặc rảnh tay và ngắt lời Mira khi đang nói. Mira nhớ điều anh kể qua nhiều ngày
(trí nhớ dài hạn, lưu ở máy, xem/xóa được trong nút **Trí nhớ**). Mira chủ động: tự chào khi anh quay lại và
hỏi thăm một lần khi anh im lâu.
"Não" của nhân vật chọn được: **model local qua Ollama** (miễn phí, offline) hoặc **Claude API**.
Không cần Node.js: thư viện frontend đã được vendor sẵn trong `web/vendor/`.

## Chạy thử

Cần [uv](https://docs.astral.sh/uv/) (quản lý Python 3.12 + thư viện cho dự án).

1. `uv sync` (lần đầu: tạo `.venv` với Python 3.12 và cài thư viện).
2. Copy `.env.example` thành `.env` (mặc định dùng Ollama).
3. Chọn não:
   - **Ollama (không cần API):** cài Ollama từ ollama.com (`winget install Ollama.Ollama`), mở app. Trên máy này app tray không bật được server (log báo "timeout waiting for Ollama server to be ready"), nên đã đặt file `ollama-serve.vbs` vào thư mục Startup (`Win+R` → `shell:startup`) để chạy ẩn `ollama serve` mỗi lần đăng nhập. Xóa file đó để tắt tự chạy. Máy khác thì mở một terminal chạy `ollama serve` và để nguyên. Sau đó chạy `ollama pull qwen3:8b` ở terminal khác. Trang web sẽ báo ngay khi mở nếu Ollama chưa chạy hoặc chưa có model.
   - **Claude:** đặt `LLM_PROVIDER=claude` và điền `ANTHROPIC_API_KEY` trong `.env`.
4. Giọng nói: mặc định **VieNeu-TTS v3 Turbo** (Apache-2.0, CPU, không tốn VRAM), giọng `Mỹ Duyên`. Lần chạy đầu
   tự tải model từ Hugging Face rồi nạp (~10s mỗi lần bật server). Nút **Giọng: bật/tắt** trên trang; lựa chọn được nhớ.
   Muốn dùng Piper (nhẹ hơn, giọng cứng hơn): `TTS_PROVIDER=piper` rồi `uv run python scripts/get_voice.py`.
5. Có model nhân vật: tạo bằng **VRoid Studio** → Export → VRM, rồi đặt vào `web/models/waifu.vrm`
   (hoặc kéo thả file `.vrm` vào trang web).
6. `uv run uvicorn app.main:app --reload --port 8000` → mở http://localhost:8000

Sửa `.env` xong thì phải **tắt và chạy lại server**: `--reload` chỉ theo dõi file `.py`.

Test:
- `uv run pytest` (dùng LLM, Ollama và giọng giả, không gọi model thật).
- `uv run python scripts/verify_memory.py` (trí nhớ với model thật; chỉ chạy khi trí nhớ đang trống, tự dọn sau khi xong).
- `uv run python scripts/verify_stt.py` (nghe giọng nói với server thật: độ trễ, WER, im lặng/tiếng ồn).
- `uv run python scripts/verify_live.py --warmup [--voice]` (test với model thật: đo độ trễ chữ và audio, tag cảm xúc,
  kiểm tra tag/emoji lộ ra hoặc bị đọc).
- Mỗi lượt chat ghi một dòng vào `logs/turns.jsonl`: thời gian tới chữ đầu, audio đầu, tổng, model, lỗi. Không ghi nội dung.
- Số liệu đo TTS/STT/LLM trên máy này: `spikes/audio/KET_QUA.md`.

## Cấu trúc

| File | Vai trò |
|---|---|
| `app/main.py` | FastAPI: `POST /api/chat` stream SSE, `GET /api/health`, phục vụ thư mục `web/` |
| `app/llm.py` | `ClaudeLLM` và `OllamaLLM`, cùng hợp đồng `stream()`; `make_llm()` chọn theo `LLM_PROVIDER` |
| `app/persona.py` | System prompt: tính cách nhân vật + quy ước tag cảm xúc |
| `app/emotion_tags.py` | Tách tag `[happy]`… khỏi luồng text (kể cả tag bị cắt giữa 2 chunk) |
| `app/speech_text.py` | Tách câu trả lời thành đoạn để đọc sớm (đoạn đầu cắt ở dấu phẩy), lọc emoji/ký hiệu |
| `app/tts.py` | Hợp đồng `SpeechEngine` (stream PCM theo mảnh) + `VieNeuTTS`, `PiperTTS`; `make_tts()` chọn theo `TTS_PROVIDER` |
| `app/turn_log.py` | Ghi `logs/turns.jsonl` |
| `web/avatar.js` | Scene 3D, nạp VRM, idle (thở, chớp mắt, lắc đầu), biểu cảm, miệng theo nguyên âm + âm lượng, gật/nghiêng đầu theo nhịp nói, cảm xúc và khi lắng nghe |
| `web/lipsync.js` | Nguyên âm chính từng âm tiết tiếng Việt → khẩu hình aa/ih/ou/ee/oh; bắt nhịp âm tiết từ âm lượng |
| `web/audio_player.js` | Phát giọng theo từng mảnh PCM (Web Audio), đo âm lượng cho nhép miệng, dừng khi gửi tin mới |
| `web/chat_client.js` | Đọc SSE từ server |
| `app/memory.py` | Trí nhớ dài hạn: kho `data/memory.json`, luật thay/cộng theo loại, trích xuất bằng LLM, dựng system prompt có ngày giờ |
| `app/presence.py` | Mira chủ động: lần nói cuối/lần chào cuối (`data/presence.json`), khi nào chào/hỏi thăm, lời nhắc ẩn cho model |
| `app/stt.py` | Hợp đồng `SpeechRecognizer` + `ZipformerSTT` (mặc định, có Silero VAD chặn im lặng) + `WhisperSTT` (dự phòng) |
| `web/mic.js`, `web/mic_worklet.js` | Ghi âm PCM 16kHz, giữ để nói, rảnh tay (VAD theo năng lượng) |
| `web/main.js` | Giao diện chat, nút giọng/mic/rảnh tay, ngắt lời Mira, lưu lịch sử vào localStorage |
| `web/vendor/` | three.js 0.187 + three-vrm 3.5.5 (MIT, xem `VERSIONS.txt`) |

### Giao thức SSE `/api/chat`

Request: `{messages, voice}` (`voice` mặc định `false`).

`{type:"emotion", emotion}` · `{type:"text", text}` (đã bỏ tag) ·
`{type:"audio", seq, part, rate, pcm, text?, emotion?}` (PCM 16-bit base64 theo mảnh, chỉ khi `voice`) ·
`{type:"text_done", raw}` (chữ xong, giọng có thể còn đang tạo) · `{type:"tts_error", message}` (không kết thúc
stream) · kết thúc bằng `{type:"done", raw}` (câu gốc còn tag, client lưu vào lịch sử) hoặc `{type:"error", message}`.
Chi tiết: `specs/002-voice-tts/contracts/chat-sse.md`.

`POST /api/stt`: body PCM 16-bit 16kHz mono → `{text, audio_ms, ms}` (xem `specs/003-voice-input-stt/contracts/stt.md`).

## Cấu hình (`.env`)

- `LLM_PROVIDER`: `ollama` (mặc định, kể cả khi không có `.env`) hoặc `claude`.
- Ollama:
  - `OLLAMA_MODEL`: mặc định `qwen3:8b`, vừa GPU 8GB.
  - `OLLAMA_URL`: mặc định `http://127.0.0.1:11434`.
  - `OLLAMA_THINK=false`: tắt chế độ suy nghĩ của Qwen 3 cho nhanh. Để trống nếu model không hỗ trợ.
  - `OLLAMA_KEEP_ALIVE`: giữ model trong VRAM bao lâu, mặc định `30m`.
  - `OLLAMA_TEMPERATURE`: mặc định `0.8`.
- Claude:
  - `ANTHROPIC_API_KEY`: key lấy ở console.anthropic.com.
  - `CLAUDE_MODEL`: mặc định `claude-opus-5-5`.
  - `CLAUDE_EFFORT`: `low` (mặc định), `medium`, `high`.
  - Server bật sẵn *server-side fallback*: nếu model chính từ chối một câu vì bộ lọc an toàn, API tự thử model dự phòng.
- Giọng nói:
  - `TTS_PROVIDER`: `vieneu` (mặc định), `piper` hoặc `none`.
  - `VIENEU_VOICE`: mặc định `Mỹ Duyên`; giọng nữ khác: Trúc Ly, Thục Đoan, Đoan Trang, Kim Thanh, Mai Anh…
  - `VIENEU_PRECISION`: `fp32` (mặc định) hoặc `int8` (trên máy này không nhanh hơn rõ).
  - `PIPER_VOICE`: đường dẫn file `.onnx`, mặc định `models/piper/vi_VN-vais1000-medium.onnx`.
  - `PIPER_LENGTH_SCALE`: `>1` đọc chậm hơn, `<1` nhanh hơn.

- Nghe giọng nói:
  - `STT_PROVIDER`: `zipformer` (mặc định), `whisper` hoặc `none`.
  - `ZIPFORMER_DIR`: thư mục model Zipformer-30M-RNNT-6000h (CC-BY-NC-ND-4.0, chỉ dùng cá nhân); mặc định `models/zipformer`,
    tải bằng `uv run python scripts/get_stt_model.py`. Máy này dùng bản có sẵn của VoiceDeck ở `D:\voice_models\Zipformer-30M-RNNT-6000h`.
  - Khi dùng Whisper:
  - `WHISPER_MODEL` (`small`), `WHISPER_DEVICE` (`cpu`; `cuda` cần cuBLAS/cuDNN + VRAM trống), `WHISPER_THREADS` (12).

- Trí nhớ: `MEMORY_ENABLED` (`true` mặc định). Dữ liệu ở `data/memory.json`, không vào git.

- Mira chủ động: `PROACTIVE_GREETING` (true), `GREET_MIN_GAP_MINUTES` (30), `PROACTIVE_CHECKIN_MINUTES` (10, 0 = tắt).

- Từ đánh thức cho Rảnh tay: `HANDSFREE_WAKE_WORD` (true), `WAKE_WINDOW_SECONDS` (60). Đã im quá 60 giây thì phải mở đầu
  bằng "Mira ơi / Mira à / Này Mira / Ê Mira…" Mira mới trả lời; đang trò chuyện hoặc giữ để nói thì không cần.

## Giới hạn hiện tại

- Lời chào khi mở trang chỉ có chữ nếu trình duyệt chưa cho phát âm thanh (chưa bấm gì vào trang).
- Model 8B đôi khi tự thêm chi tiết nhỏ khi chào/hỏi thăm dù đã dặn không bịa.
- Từ đánh thức nhận tên theo chữ STT ghi ra, nên chấp nhận vài cách nghe nhầm ("Vera ơi", "Misa ơi"…). Mở đầu câu bằng
  "Visa ơi"/"Mara ơi" thật cũng sẽ đánh thức Mira; "Ê Mira" đôi khi bị nghe thành "Camera" và bị bỏ qua.

- Giọng chưa đổi theo cảm xúc của câu (VieNeu có tag `[cười]`… đang thử nghiệm, chưa dùng). Giọng riêng là spec 004
  (VieNeu bắt chước được giọng từ mẫu 3–8s).
- Câu trả lời dài giữ CPU bận tạo giọng (~0,45 giây cho mỗi giây audio).
- Nghe giọng nói đo trên giọng người thật (FLEURS): sai ~9% số từ. Chưa đo bằng mic laptop của người dùng sau khi đổi sang Zipformer. Chế độ rảnh tay
  dựa vào khử tiếng vọng của trình duyệt: dùng tai nghe sẽ chắc ăn hơn.
- Sau khi Ollama nghỉ (`OLLAMA_KEEP_ALIVE`, mặc định 30 phút) model bị nhả khỏi GPU. App tự nạp lại ở nền lúc khởi động
  và mỗi lần mở trang (~4s), nên nếu gửi tin ngay trong vài giây đầu thì câu đó vẫn chậm hơn (đo: 4,6s so với 0,6s).
- Trí nhớ dài hạn chỉ lưu "điều đáng nhớ" do model 8B tự trích: đôi khi sót ý khi một câu có nhiều ý; sai thì xóa trong
  nút Trí nhớ. Lịch sử gửi model được cắt theo ~5000 ký tự để vừa ngữ cảnh 4096 token.
- Cử động vẫn tự sinh bằng code (thở, chớp mắt, dáng đầu theo cảm xúc, gật theo nhịp); chưa có animation tay/thân.
- Thêm `?debug=1` vào địa chỉ trang để lộ `window.__mira.avatar` khi cần đo/gỡ lỗi.
- Model local nhỏ đôi khi quên tag cảm xúc hoặc tự chế tag (vd `[concerned]`). Tag tự chế hay gặp được quy về cảm xúc gần nhất
  (`app/emotion_tags.py`, `ALIASES`), tag lạ còn lại bị bỏ đi để không hiện ra hay bị đọc thành tiếng.
