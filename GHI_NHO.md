# GHI NHỚ DỰ ÁN — Mira – 3D Vietnamese Voice Companion

(Đổi tên từ "Waifu Chat" ngày 14/11/2026. Thư mục vẫn là `Waifu_chat`, khóa localStorage vẫn `waifu-*` để không mất lịch sử/cài đặt.)

## Trạng thái hiện tại

- Hướng đã chốt: **Hướng 1 — web Three.js + VRM** trước; xong thì sang **Hướng 4** (tham khảo/fork dự án mã nguồn mở như Open-LLM-VTuber, AIRI, ChatVRM, Amica).
- **Stack hiện tại: Python, không còn Node.** Python 3.12.16 do uv quản lý (`.venv`, `.python-version`, `pyproject.toml`, `uv.lock`). FastAPI + uvicorn, `anthropic` SDK 2.8.0 (model `claude-opus-5-5`, effort `low`, server-side fallback `"default"`). Frontend JS thuần + importmap, thư viện vendor trong `web/vendor/`.
- **Có 2 "não", chọn bằng `LLM_PROVIDER` trong `.env`:** `ollama` (mặc định, model local `qwen3:8b`, gọi API gốc `/api/chat` NDJSON bằng httpx) hoặc `claude`. `.env` được tạo từ `.env.example` (mặc định `LLM_PROVIDER=ollama`).
- Tách tag cảm xúc đã chuyển lên server (`app/emotion_tags.py`), để TTS nhận text sạch.
- **Giọng nói (spec 002, xong trừ T013):**
  - Mặc định **VieNeu-TTS v3 Turbo, giọng Mỹ Duyên** (người dùng chọn sau khi nghe mẫu), CPU/ONNX, không tốn VRAM. Piper còn làm dự phòng (`TTS_PROVIDER=piper`).
  - Hợp đồng `SpeechEngine.stream()` trả PCM theo mảnh. `Speaker` chạy nền nên chữ không chờ giọng. Event `audio` dạng PCM theo mảnh, thêm `text_done` (cho gửi tin mới khi chữ xong).
  - Frontend phát PCM theo mảnh. Miệng tự cân theo đỉnh âm lượng. Nút "Giọng: bật/tắt". Log `logs/turns.jsonl`.
  - Đo thật: audio đầu 0,53–0,61s, chữ đầu 0,13–0,15s, 0 lỗ hổng khi phát, VRAM không đổi.
  - Miệng nhép trên VRM thật đã kiểm chứng (T013). Người dùng chưa nghe bản chạy trong app.
- `uv run pytest` hiện là **210/210 pass** (2026-11-22, nhánh `feat/011-japanese-voice`).
- **Nghe giọng nói (spec 003):** mặc định **Zipformer-30M** (sherpa-onnx, CPU, model đặt ngoài repo, trỏ bằng `ZIPFORMER_DIR`; máy dev dùng chung bản của VoiceDeck), có Silero VAD chặn im lặng; Whisper `small` làm dự phòng. Nút "Giữ để nói" (hoặc giữ Space khi ô nhập trống), "Rảnh tay" (VAD theo VoiceDeck), người dùng nói thì Mira im. Đo: FLEURS người thật WER 8,8% / 0,18s. **Chưa thử lại mic thật sau khi đổi.**
- **Trí nhớ dài hạn (spec 004):** `app/memory.py`, `data/memory.json` (gitignored). Model chỉ đề xuất điều mới + loại; code tự thay theo loại (tên, tuổi, nghề, nơi ở, cách gọi) và ghi ngày nói. System prompt có ngày giờ + điều đã nhớ. Lịch sử cắt theo 5000 ký tự. Nút "Trí nhớ" xem/xóa. Kiểm chứng thật đạt hết (`scripts/verify_memory.py`).
- **Mira chủ động (spec 006):** `app/presence.py`, `POST /api/proactive {kind: greet|checkin}` (204 nếu chưa đến lúc). Chào khi mở trang nếu vắng ≥ 30 phút; hỏi thăm 1 lần khi im ≥ 10 phút (trang hiện, không bận). Mốc thời gian trong trí nhớ được code đổi thành ngày + nhãn đã diễn ra/hôm nay/sắp tới.
- **Từ đánh thức (spec 007):** `app/wake.py` nhận "Mira ơi" mờ (STT hay nghe thành Vera/Misa/Mara/"mới ra"/Emmira); `/api/stt` trả `wake` và sửa tên về "Mira". Rảnh tay + im > `WAKE_WINDOW_SECONDS` (60) thì câu không gọi tên bị bỏ qua lặng lẽ, ô nhập gợi ý gọi tên. Giữ để nói không bị ảnh hưởng.
- **Giọng theo cảm xúc (spec 008):** `app/voice_style.py`. Câu vui chèn `[cười]`, câu buồn `[thở dài]` (tín hiệu VieNeu, mỗi loại 1 lần/120s, chỉ engine có `supports_cues`); event audio có `speed` (vui 1.05, buồn 0.94) → trình duyệt đổi `playbackRate`. Tag cảm xúc giờ là ranh giới đoạn đọc (trước đây câu đứng ngay trước tag bị gán cảm xúc mới). **Người dùng chưa nghe.**
- **Trí nhớ sâu hơn (spec 009):** `app/episodes.py`, `data/episodes.json`. Server ghi buổi đang nói; im > 30 phút thì tóm tắt 1–3 câu (hẹn giờ trong server; server tắt thì tóm tắt bù ở lượt sau, lời chào chờ). Prompt kèm 3 buổi gần nhất. `MemoryStore.expire_events` bỏ sự kiện đã qua > 14 ngày.
- **Git:** repo khởi tạo 2026-11-14, nhánh `main`. `.claude/settings.local.json`, `.env`, model, log không vào git.
- **Đã kiểm chứng với qwen3:8b thật (spec 001):**
  - `uv run pytest` 20/20 pass (lúc đó).
  - `scripts/verify_live.py --warmup`: chữ đầu ≤ 2s ở 5/5 câu, 5/5 câu có tag, không lộ tag.
  - Trình duyệt: chữ hiện dần, tải lại trang vẫn còn lịch sử.
  - Model chưa pull thì báo đúng lệnh `ollama pull` (T017, chạy với Ollama thật).
  - Nhớ ngữ cảnh 2 lượt (tên, sở thích).
- **Chất lượng sau khi sửa (đo với qwen3:8b thật):**
  - Không còn dấu cách đôi; chữ lúc stream và sau khi tải lại trang giống hệt nhau.
  - Xưng hô sai: 1/24 câu (trước khi sửa prompt là 2/24 đến 2/5). Lỗi hay gặp khi người dùng nói "mình". Đổi temperature 0,8 → 0,5 không giúp rõ.
  - Nhớ ngữ cảnh: 3/3 lần đúng, không bịa chuyện của người dùng.
- **Avatar:** `web/models/waifu.vrm` là `Mira.vrm` người dùng tự làm trong VRoid (VRM 1.0, texture Shrinked ~59MB VRAM, gitignored; bản gốc `.vroid` giữ riêng trên máy người dùng). Tay buông, biểu cảm, chớp mắt, nhép miệng đều đã kiểm chứng (T020, T013). Model có thêm khẩu hình `ee/ih/oh/ou` chưa dùng.
- Spec Kit 1.4.0: `constitution.md`, `spec.md`, `plan.md`, `research.md`, `contracts/`, `quickstart.md`, `tasks.md`.
- **Ollama 0.40.16**: app tray báo timeout, server không lên. Đang chạy được bằng `ollama serve` mở tay. Đã pull **qwen3:8b** (5,2GB, Q4_K_M).
- Lưu ý: `--reload` của uvicorn không theo dõi `.env`; sửa `.env` thì phải khởi động lại server. Sau `uv sync` (đổi nhiều file trong `.venv`), bộ reload có thể đứng: code mới không được nạp. Kiểm tra bằng `/api/health` hoặc khởi động lại server. Trên Windows, kết nối tới cổng chưa mở mất khoảng 2 giây mới báo lỗi (hành vi của TCP, không phải bug).
- Máy: RTX 5070 Laptop 8GB VRAM; Ollama detect 6.8GB available. Python hệ thống 3.9/3.10 + anaconda vẫn còn, không dùng cho dự án này.

## Việc tiếp theo

**Cập nhật 2026-11-21** (danh sách đang dùng; kế hoạch 13/11 bên dưới giữ làm lịch sử):

- ~~Chuyển động đầu theo giọng nói~~ (xong lần 33, spec 010). Bước tiếp theo hợp lý: chuyển động thân bằng VRMA, dùng gói CC0 Sachi (người dùng tự tải zip trên BOOTH, cần đăng nhập).
- **Hợp giao cho Antigravity** (luật chung ở `AGENTS.md`; mỗi agent một nhánh, không sửa trùng file):
  - Quay GIF/video demo cho README.
  - ~~Tìm file chuyển động VRMA có license rõ ràng~~ (xong lần 32, xem nhật ký).
  - ~~Dọn backend, mục 6–10 của audit~~ (Claude làm xong ở lần 31).
  - ~~Viết README tiếng Anh~~ (xong lần 32: `README.en.md`).
- **Người dùng tự làm:** thử mic và loa thật; nghe giọng theo cảm xúc; ẩn email trên hồ sơ GitHub; chuyển `CV_Projects_AIML.md` ra khỏi repo.
- **Chưa kiểm chứng thật:** hẹn giờ tóm tắt buổi sau 30 phút im.
- **Để sau:** body animation (VRMA); tự chạy khi bật máy + Tailscale (`start.bat` đã có, lần 33); giọng riêng (spec 004 cũ); nhiều người dùng; graphify.

Kế hoạch đề xuất sau rà soát 2026-11-13 (chờ người dùng chốt):

**Ràng buộc chính:** khi `qwen3:8b` đã nạp, VRAM dùng 7,39/8,15GB, chỉ còn khoảng 0,76GB. TTS và STT không chạy thêm trên GPU được, trừ khi đổi sang LLM nhỏ hơn.

0. ~~Dọn nhỏ~~ (xong phiên 7). App tray Ollama vẫn không bật được server. Đã cho `ollama serve` tự chạy khi đăng nhập (phiên 8).
1. ~~T020~~ (xong phiên 15): spec 001 và 002 đã xong hết task.
2. ~~Đo trước khi chọn~~ (xong phiên 9; số liệu ở `spikes/audio/KET_QUA.md`). Đề xuất, chờ người dùng chốt:
   - **Spec 002** dùng Piper `vi_VN-vais1000-medium`: chạy CPU, audio đầu tiên trong 0,04s, CC-BY-4.0. Giữ `qwen3:8b`.
   - **Spec 004 (giọng riêng)** dùng F5-TTS tiếng Việt: chạy GPU, khoảng 1,4s/câu, đọc rõ hơn Piper, license phi thương mại.
     - Muốn vừa VRAM phải đổi sang `qwen3:4b-instruct` (đã đo: nhanh, đủ tag, nhưng hay chèn emoji).
     - Cần một đoạn mẫu giọng sạch 5–10s, có quyền dùng.
   - viXTTS: bỏ (cần fork cũ, không chạy RTX 5070).
3. ~~Spec 002 – TTS~~ (xong phiên 11, còn T013 cần VRM). Khi sang F5-TTS (~1,4s/câu): chuyển tạo giọng sang worker nền để chữ không bị chặn (ghi trong `specs/002-voice-tts/plan.md`).
4. ~~Spec 003 – STT~~ (xong phiên 16). Còn: người dùng thử mic thật. Ý cải thiện: nạp sẵn LLM khi mở trang (sau khi Ollama nghỉ, câu đầu chậm ~9s); Whisper GPU nếu muốn nhanh hơn (0,25s) nhưng VRAM chật.
5. **Spec 004 – giọng riêng của Mira:** cần người dùng chốt nguồn giọng mẫu có quyền dùng.
   - Không dùng GPT-SoVITS (theo hiểu biết hiện tại, không hỗ trợ tiếng Việt).
   - Không dùng Common Voice (nhiều người nói; bản trên HF đã trống).
6. ~~Trí nhớ dài hạn~~ (xong phiên 19). Có thể thêm sau: tóm tắt hội thoại cũ; sự kiện hết hạn; tăng ngân sách lịch sử (prompt thật mới 2465/3584 token).
7. **Hướng 4:** đào sâu hơn sau khi có giọng nói.

## Tham khảo: Animates (animates.ai, Animation Inc.), đọc 2026-11-13

Nguồn: trang chủ và `/privacy` (bản sửa 2026-09-07). Họ không công bố kỹ thuật avatar.

**Cách họ làm:** 100% cloud.
- App native cho iOS, Android, Mac, Windows. Backend trên Google Cloud, Cloudflare ở biên.
- LLM qua nhiều nhà cung cấp, chọn theo tính năng và tình trạng sẵn có: SpaceXAI API (có vẻ là API Grok), Gemini/Vertex, Amazon Bedrock, Cloudflare Workers AI, Cerebras (suy luận rất nhanh), OpenRouter, FriendliAI, DeepInfra, Claude (dùng cho thị giác).
- STT: SpaceXAI, Google, Amazon Transcribe, Soniox (STT stream). TTS: SpaceXAI.
- Các phần khác:
  - Nhớ hội thoại cũ để cá nhân hóa.
  - Chụp màn hình theo chu kỳ, gửi cho model thị giác.
  - Tìm web qua Exa.
  - Theo dõi LLM bằng Langfuse.

**Ý hợp với máy mình** (đã cân nhắc ràng buộc 8GB VRAM):
1. Ghi log từng lượt (độ trễ STT/LLM/TTS, model, lỗi) ra JSONL. Bản nhẹ của Langfuse, không tốn VRAM → đưa vào spec 002.
2. Ưu tiên tốc độ hơn độ thông minh: họ dùng cả Cerebras, khớp với constitution II. Đúng hướng model nhỏ + đọc câu đầu sớm.
3. Nhiều nhà cung cấp có dự phòng: `ChatLLM` đã sẵn. Có thể thêm chế độ "local trước, lỗi thì sang Claude" (chỉ khi người dùng bật).
4. Trí nhớ dài hạn: tóm tắt + danh sách sự thật về người dùng, chèn vào prompt có giới hạn token (context Ollama đang 4096).
5. STT stream (như Soniox): để sau, khi bản bấm-giữ-để-nói đã ổn.

**Không hợp lúc này:**
- Chụp màn hình + model thị giác local: thêm vài GB VRAM.
- App native nhiều nền tảng.
- Định tuyến nhiều nhà cung cấp cloud (trái local-first).

## Nhật ký phiên

### 2026-11-22 (lần 36): làm nốt việc còn dở của lần 35 (nhánh `fix/viec-con-do`)
- `logs/turns.jsonl` quá 5MB thì đổi sang `turns.1.jsonl` (chỉ giữ một file cũ) – `app/turn_log.py`.
- Tóm tắt buổi trò chuyện hỏng 3 lần liền thì bỏ buổi đó (log `error: gave_up`), không giữ lượt mãi – `app/episodes.py`.
- VOICEVOX tắt: server gửi sự kiện `voice_off` đầu luồng; trình duyệt nhép miệng theo chữ như khi lỗi giọng nhưng không
  hiện bong bóng lỗi (`web/chat_client.js`, `web/main.js`). Thử thật: VOICEVOX tắt -> chỉ chữ, không `<ja>`; bật lại
  -> lượt đầu vẫn chỉ chữ (kiểm ở nền), từ lượt sau có giọng.
- Đo lại lúc máy rảnh (tab avatar 3D đã đóng, không chạy gì song song): **giọng đầu trung vị 1,64s, chữ đầu 144ms,
  câu bị im 6/45 (13%), 15/20 câu trả lời đủ giọng**, 0 lần lọt chữ Nhật. Lần đo 4,1s trước đó là do máy bận.
- Còn lại: người dùng nghe thử; hẹn giờ tóm tắt sau 30 phút im vẫn chưa kiểm thật; các việc cần người dùng tự làm ở
  "Việc tiếp theo".

### 2026-11-22 (lần 35): review toàn nhánh spec 011 + rà soát cả project, sửa lỗi
- Review toàn nhánh do Antigravity (Claude Opus Medium) làm. Headless `agy` chặn mọi lệnh shell kể cả khi có
  `--settings` cho phép lệnh đọc; cách chạy được: gom prompt + spec + diff vào một file rồi đưa qua stdin, dặn không
  gọi công cụ nào. PowerShell 5.1 cắt chuỗi prompt có ngoặc kép, nên gọi `agy` từ Bash.
- Đã sửa (`app/ja_tags.py`, `app/main.py`, `app/tts.py`, `app/llm.py`, `web/main.js`):
  - Model quên `</ja>`: thẻ `<ja>` mới đóng thẻ cũ; chữ Việt sót sau dấu hết câu Nhật trả về màn hình (chỉ khi phần đó
    không còn kana/kanji, để "はい。OKです" vẫn đọc trọn).
  - Câu trong `<ja>` bỏ tag cảm xúc; không có kana/kanji (model quên dịch) thì không đọc.
  - `trim_history`: bỏ `<ja>` trước khi đo ngân sách; lượt toàn tiếng Nhật gửi `"…"`.
  - VOICEVOX tắt (`VoicevoxTTS.down`): lượt đó chỉ có chữ, không bắt model viết tiếng Nhật, kiểm lại ở nền.
  - Nhỏ: Claude không bị hạ `max_tokens` xuống 1024; `tts.check()` chạy trong thread; lịch sử giữ xuống dòng;
    nguyên âm vô thanh viết hoa của VOICEVOX vẫn mấp máy miệng; regex bỏ ký tự ẩn U+3040.
- Prompt tiếng Nhật thêm "trả lời 1–3 câu, câu cuối cũng phải có `<ja>`". `scripts/verify_ja_voice.py` giờ đếm câu
  Việt không có `<ja>` theo sau. Đo 20 câu: câu bị im 16/55 (29%) -> 12/51 (24%), trả lời không im câu nào 8/20 ->
  10/20 (n nhỏ, có thể là nhiễu). Giọng đầu lần đo sau chậm (4,1s) do máy bận chạy việc khác giữa chừng, cần đo lại.
- Còn lại: đo lại độ trễ khi máy rảnh; `logs/turns.jsonl` không giới hạn dung lượng; episodes giữ lượt mãi nếu tóm
  tắt hỏng liên tục; khi VOICEVOX tắt miệng Mira đứng yên (trình duyệt vẫn chờ giọng). Chưa squash-merge vào main.

### 2026-11-21 (lần 34): spec 011 chat tiếng Việt, giọng tiếng Nhật (VOICEVOX ずんだもん)
- Người dùng chọn: chữ tiếng Việt, giọng tiếng Nhật; engine VOICEVOX (đã nghe 10 giọng, chọn ずんだもん); model tự viết kèm
  `<ja>…</ja>` (không gọi dịch riêng); nếu chậm thì rút gọn rồi báo. Thiết kế + kế hoạch: `specs/011-japanese-voice/`.
- Nhánh `feat/011-japanese-voice`:
  - Bước 1–3 do subagent làm + review từng bước (`app/ja_tags.py`, `VoicevoxTTS` trong `app/tts.py`, ghép vào
    `app/main.py`/`memory.py`/`llm.py`). Review bắt 4 lỗi thật: ngoặc trống sót khi chữ bị cắt, thẻ lạc lọt màn hình,
    warm_up chưa tổng hợp thử, câu Nhật nhận sai cảm xúc khi tag cảm xúc nằm cùng mảnh. Subagent tốn ~910k token →
    người dùng thấy đắt; việc cỡ này lần sau Claude tự làm, review một lần cuối.
  - Bước 4 (giao diện): giao Antigravity (Claude Opus Medium) 2 lần đều dừng giữa chừng, không sửa file nào (log:
    "You are not logged into Antigravity" khi chạy 2 `agy` cùng lúc) → Claude tự làm: `moraVisemes`, lịch sử bỏ `<ja>`,
    dòng `VOICEVOX:ずんだもん` cạnh nút Giọng. Kiểm trong trình duyệt với model + VOICEVOX thật.
  - Tài liệu (README, README.en, `.env.example`): Antigravity (Gemini 4 Argon Medium) viết, Claude soát.
  - Đo 20 câu thật (`scripts/verify_ja_voice.py`, server thử cổng 8002 tắt trí nhớ): lần 1 giọng đầu trung vị 2,9s (vượt
    mốc 2,5s); rút gọn prompt (`JA_VOICE_PROMPT`: câu nào cũng phải có `<ja>`, tiếng Nhật thật ngắn, tên riêng/món ăn viết
    katakana theo âm Việt) → **giọng đầu 1,6s**, chữ đầu 145ms, 0 lần lọt chữ Nhật. Nhưng **chỉ 8/20 câu trả lời có `<ja>`
    cho mọi câu** (câu thiếu thì im), bản dịch của qwen3:8b đôi khi sai nghĩa/cứng (đã báo người dùng).
- Cách bật trên máy này: chạy `run.exe` trong thư mục `tools/voicevox/engine` ở thư mục người dùng (ngoài repo) (VOICEVOX 0.26.2, CPU), rồi
  `TTS_PROVIDER=voicevox`. `.claude/launch.json` có cấu hình `voicevox` (đường dẫn riêng, **không commit**) và `waifu-ja`.
- Lúc thử, server cổng 8002 vẫn ghi `data/presence.json` (giờ nói lần cuối) dù tắt trí nhớ.
- Còn lại: người dùng nghe thử và quyết có chấp nhận tỉ lệ câu im không; review toàn nhánh; gộp/push khi người dùng đồng ý.

### 2026-11-21 (lần 33): chuyển động đầu (spec 010) + `start.bat` do Antigravity viết
- **Spec 010** (`specs/010-head-motion/spec.md`, chỉ một file vì việc nhỏ). `web/avatar.js`:
  - Đang nói: cứ 0,8–2 giây đổi hướng đầu mới nhỏ (quay ≤ 0,08 rad, ngẩng/cúi ≤ 0,03 rad, chia cổ 40% / đầu 60%), im thì về giữa.
  - Gật theo độ nhấn: `0,015 + 0,035 × (âm lượng / đỉnh gần đây)` thay cho 0,035 cố định.
  - Mắt: `lookAt.target` là một điểm `gaze` bám camera; cứ 3–7 giây liếc sang ngang/xuống 0,4–1,2 giây. Đang lắng nghe thì không liếc.
  - Đo trong trình duyệt (server thử `waifu-test` ở cổng 8001, tắt lời chào và trí nhớ nên không đụng `data/` hay lịch sử ở cổng 8000; giọng giả 220Hz to nhỏ theo nhịp): đầu quay −0,033…0,041 rad khi nói, về 0 khi im; 16 âm tiết trong 4s, gật tối đa 0,034; lắng nghe 0 khung liếc, lúc rảnh có liếc; console không lỗi. **Người dùng chưa xem bằng mắt.**
- `.claude/launch.json` thêm cấu hình `waifu-test` (cổng 8001, `PROACTIVE_GREETING=false`, `MEMORY_ENABLED=false`) để thử giao diện mà không đụng dữ liệu thật.
- **`start.bat`** (Antigravity, Claude Opus 5.5 Medium, `accept-edits`): kiểm tra uv, bật `ollama serve` nếu chưa chạy (bỏ qua khi `LLM_PROVIDER=claude`), chạy server không `--reload`, mở trình duyệt khi `/api/health` trả lời; Mira chạy sẵn thì chỉ mở trình duyệt. README/README.en thêm một dòng.
  - Lần giao đầu thất bại: `agy -p` không hỏi được quyền chạy lệnh nên tự từ chối và dừng. Giao lại kèm câu "không được chạy lệnh shell, chỉ đọc/ghi file" thì xong.
  - Claude kiểm: file UTF-8 không BOM, đổi LF → CRLF; chạy nhánh "không có uv" in đúng tiếng Việt và dừng. **Chưa chạy trọn** (sẽ bật server và mở trình duyệt của người dùng).

### 2026-11-21 (lần 32): giao việc cho Antigravity qua CLI `agy`
- Máy có CLI `agy` (Antigravity, tài khoản Google của người dùng). Chạy không tương tác:
  `agy -p "<việc>" --model <model> --mode plan|accept-edits --print-timeout 20m`. `agy models` liệt kê model:
  Gemini 4 Neon/Argon/Hydrogen, Gemini 3.8 Flash, Claude Opus/Sonnet 5.5, GPT-OSS 120B. Hạn mức tính riêng ở
  Antigravity (Gemini một nhóm, Claude + GPT một nhóm), không trừ vào gói Claude Code. Đã thử: Claude Sonnet 5.5 và
  Gemini 3.8 Flash đều trả lời được. Antigravity tự đọc `AGENTS.md`.
- **README tiếng Anh:** Gemini 4 Neon (`accept-edits`, nhánh `agy/readme-en`) viết `README.en.md`, chỉ tạo đúng file đó.
  Claude soát: đủ mục, có cả `--extra piper`, `ALLOWED_HOSTS`, bảng license. README.md thêm dòng trỏ sang bản tiếng Anh.
- **Nguồn chuyển động VRMA** (Gemini 3.8 Flash, `plan`, chỉ đọc). Claude kiểm lại trang gốc:
  - **[CC0]Sachi VRMA 1** (booth.pm/en/items/6412084): trang gốc ghi CC0 (**đã kiểm**). Zip 56MB, 2 thư mục
    `handmade_vrma` và `capture_vrma`. Tên từng file (Gemini kể `idle_pose`, `greet_sachi`…) **chưa kiểm**, phải tải zip mới biết.
    → Ứng viên số 1 để đưa thẳng vào repo.
  - three-vrm examples: chỉ có `test.vrma` kỹ thuật (MIT), không dùng được cho hội thoại.
  - VRoid Project VRMA set (booth.pm/en/items/5512385): theo Gemini cấm phân phối lại dạng trích xuất được → không đưa vào repo (**chưa kiểm**).
  - Mixamo: theo Gemini cấm phân phối file thô → chỉ cho người dùng tự tải (**chưa kiểm**). Chuyển FBX → VRMA: `fbx2vrma-converter` hoặc Blender + VRM Add-on.
  - CMU Mocap (BVH, chuyển bằng `vrm-c/bvh2vrma`): Gemini nói dùng được kèm credit; trang FAQ CMU lỗi chứng chỉ, **chưa kiểm**.
  - Quaternius: trang Gemini trích dẫn trả 404 → **không tin được** trích dẫn đó.
  - Bandai Namco Motiondataset: NC → không dùng.
  - Đề xuất: ship vài file CC0 của Sachi trong `web/animations/`; nguồn khác thì người dùng tự tải vào thư mục gitignored.
- Bài học: báo cáo license của model khác phải kiểm lại trang gốc (1 trích dẫn trỏ tới trang 404).
- **Từ nay giao việc cho Antigravity chỉ dùng 2 model** (người dùng chốt): `claude-opus-5-5-medium` (việc code, suy luận) và `gemini-4-argon-medium` (tìm hiểu, viết tài liệu).

### 2026-11-21 (lần 31): sửa nốt mục 6–10 của audit
- Nhánh `fix/audit-6-10`. Mục 11 (bỏ 2 việc không cần khỏi backlog) đã làm ở lần 30.
  6. `app/util.py` (mới): `write_json()` thay 3 bản ghi JSON nguyên tử trong `memory.py`, `episodes.py`, `presence.py`.
  7. `env_flag()` / `env_number()` thay 6 chỗ tự đọc biến môi trường (`memory`, `episodes`, `presence`, `voice_style`, `wake`). `env_number` giữ kiểu của giá trị mặc định (`EPISODE_GAP_MINUTES` và `VOICE_CUE_COOLDOWN_SECONDS` vẫn nhận số lẻ).
  8. `/api/chat` ghi lượt của anh vào buổi trò chuyện **sau khi có trả lời** (trong `after_reply`). Trước đây "não" lỗi thì anh gửi lại và lượt đó bị ghi hai lần. Test mới, đỏ trước khi sửa. Hệ quả: lượt bị ngắt trước khi Mira viết xong chữ cũng không được ghi (giống trình duyệt, vốn cũng bỏ lượt đó).
  9. `warm_llm_in_background` dùng `run_in_background`, bỏ tập task riêng; vẫn "đang nạp thì thôi".
  10. `piper-tts` (GPL-3.0) chuyển sang `[project.optional-dependencies] piper`. Dùng Piper thì `uv sync --extra piper`; thiếu thư viện thì `/api/health` báo đúng lệnh (test mới). **Lưu ý:** lần `uv sync` tới sẽ gỡ piper khỏi `.venv` (máy này đang dùng VieNeu nên không ảnh hưởng).
- Test 173 → 175 pass. Tổng `app/` gần như không đổi số dòng (+util.py, bớt lặp ở 6 file).

### 2026-11-21 (lần 30): audit toàn repo (ponytail) + sửa 5 lỗi đầu
- Người dùng bật ponytail (thay đổi nhỏ nhất, trả lời gọn) cho dự án. Audit đọc kỹ `app/` và `web/`; chưa đọc kỹ `spikes/`, `.specify/`, `scripts/`, `wake.py`, `lipsync.js`. 11 phát hiện, sửa 1–5 trên nhánh `fix/audit-1-5` (tách từ `chore/agents-md-obsidian`).
  1. **Bị ngắt lời mà Mira vẫn nói tiếp** khi chữ chưa xong: `player.stop()` chỉ xóa đoạn đang phát, đoạn audio tới sau vẫn được phát. Sửa: `interruptMira` đặt `inFlight.muted`, `onAudio` bỏ qua. Đo trong trình duyệt (mic giả bằng oscillator, `/api/chat` giả gửi 16 đoạn): code cũ phát thêm 9 đoạn sau khi ngắt, code mới 0.
  2. **Lịch sử chat phình mãi + một lượt cũ > 4000 ký tự làm mọi lượt sau 422.** Trình duyệt chỉ gửi 41 lượt (server dùng 40; dư 1 để server vẫn bỏ lời Mira mồ côi ở đầu như trước), chỉ lưu 500 lượt. Server cắt lượt cũ quá dài, chỉ từ chối tin mới nhất. Đo: gửi 41, lưu 500, tin mới 5000 ký tự vẫn 422.
  3. **File dữ liệu hỏng bị lần ghi sau đè mất:** `memory.json`, `episodes.json`, `presence.json` hỏng thì được đổi tên thành `*.json.bad` rồi mới bắt đầu rỗng. (Hỏng lần nữa thì `.bad` cũ bị thay.)
  4. **Tóm tắt trả sai dạng thì cả buổi bị vứt:** giờ giữ buổi lại, lần im sau thử lại (log `error: bad_summary`).
  5. **DNS rebinding đọc được `/api/memory`:** thêm `TrustedHostMiddleware`, biến `ALLOWED_HOSTS` (mặc định `localhost,127.0.0.1,[::1]`; dùng Tailscale thì thêm tên máy). `tests/conftest.py` thêm `testserver`. Đo bằng curl trên server thật: Host lạ 400, localhost 200.
- Test 167 → 173 (6 test mới, 5 test đỏ trước khi sửa; lỗi 1 không có test JS nên đo đỏ/xanh trong trình duyệt).
- Lúc mở trang để thử, app tự chào thật (Ollama) một lần như bình thường: lời chào đó nằm trong lịch sử trình duyệt (14 lượt) và buổi trò chuyện. Lịch sử và cài đặt Rảnh tay đã trả về như trước khi thử.
- Còn lại của audit (mục 6–11) ghi ở "Việc tiếp theo". Chưa kiểm: không có `.env` thì Ollama có bật chế độ suy nghĩ của qwen3 không (code mặc định không gửi `think`).

### 2026-11-21 (lần 29): AGENTS.md cho nhiều agent, mở repo bằng Obsidian
- Bản sửa lỗi 4–5 đã gộp vào `main` (fast-forward) và push, `main` ở `9948b89`, 167 test pass.
- Tìm hiểu DiffPoseTalk (SIGGRAPH 2024): sinh biểu cảm + chuyển động đầu bằng diffusion, ra tham số FLAME. Không hợp với Mira: repo không có LICENSE, FLAME chỉ cho phi thương mại, phải tự chuyển FLAME sang VRM, không real-time, VRAM không đủ. Thư viện dùng được với VRM: `@pixiv/three-vrm-animation` (MIT, cho thân người); wLipSync (MIT) không hơn cách nhép môi hiện tại, vì Mira đã biết trước chữ sắp đọc. Chốt: làm chuyển động đầu bằng JS trước.
- **`AGENTS.md`** (mới): luật chung cho mọi agent, gồm tiếng Việt, đọc/ghi GHI_NHO, Spec Kit, TDD, các file không được commit, quy tắc khi nhiều agent làm song song. Antigravity tự đọc `AGENTS.md` (theo tài liệu antigravity.google/docs/rules, chưa thử trong app). **`CLAUDE.md`** (mới) chỉ có `@AGENTS.md` để Claude Code nạp cùng file đó.
- **Obsidian:** đã cài từ trước nhưng chưa mở vault nào. Đã đăng ký repo làm vault (tên "Waifu_chat") và mở thử được. `.obsidian/app.json` bỏ qua `data/`, `logs/`, `models/`, `web/vendor/`, file CV. `.obsidian/` đã thêm vào `.gitignore` (git xác nhận bị bỏ qua).
- Sửa "Việc tiếp theo": thêm danh sách cập nhật 21/11, danh sách 13/11 giữ làm lịch sử.
- Chưa commit.

### 2026-11-18 (lần 28): sửa lỗi 4–5 của code review
- Nhánh `fix/background-tasks-and-ui`. Làm theo TDD (superpowers): thấy đỏ trước rồi mới sửa.
- **Lỗi 4 nặng hơn ghi chú review:** `produce()` đang `await extra` nên khi anh ngắt lời (trình duyệt đóng SSE), hủy `produce` hủy luôn việc ghi nhớ + ghi lời Mira vào buổi trò chuyện. Ngoài ra task tóm tắt trong `/api/chat` không ai giữ → GC có thể dọn khi đang chờ mạng.
  - Sửa: `run_in_background()` giữ task trong một set tới khi xong; `await asyncio.shield(extra)`. `tests/test_background.py`: ngắt lời sau `text_done` vẫn ghi nhớ xong; task tóm tắt chờ future không ai giữ vẫn sống qua `gc.collect()` (cả 2 test đỏ trước khi sửa).
- **Lỗi 5 (`web/main.js`), tái hiện trong trình duyệt bằng `/api/chat` giả lập (không đụng server/`data/`):**
  - Lời chào treo (model nạp nguội) → nút Gửi bị khóa → Enter không làm gì (HTML không cho submit ngầm khi nút mặc định bị khóa); hai câu gõ dính nhau trong ô.
  - Đang viết câu trả lời → tin gửi bằng giọng nói nằm im trong ô, Mira viết xong cũng không gửi.
  - "Não" lỗi → bong bóng tin vẫn hiện nhưng lịch sử đã bỏ, ô nhập đã xóa: mất chữ.
  - Sửa: không khóa nút Gửi nữa. Mira tự chào/hỏi thăm chưa xong → hủy, tin của anh được ưu tiên. Đang trả lời tin của anh → xếp hàng (nút "Chờ Mira…"), viết xong tự gửi. Lỗi → gỡ bong bóng, trả chữ về ô nhập, không tự gửi tin đang chờ. Nói khi ô đã có chữ chờ gửi → nối thêm, không ghi đè.
  - Kiểm lại cả 3 kịch bản sau khi sửa: đều đúng; console không lỗi. Lịch sử chat trong trình duyệt trả về như trước khi thử.
- Test 165 → 167 pass.

### 2026-11-15 (lần 27): code review toàn bộ + sửa 3 lỗi trí nhớ
- Review đọc code `app/` và `web/`. Làm trên nhánh `fix/code-review-findings`; đã commit `d8b97ed`, gộp vào `main` và push.
- **Đã sửa lỗi 1–3** (viết test đỏ trước, 4 test mới; tổng 165 pass):
  - `EpisodeStore.take_session()` chụp buổi cũ đồng bộ, `summarize(pending, llm)` gọi model; `schedule_episode_close` chụp ngay trước khi `/api/chat` ghi tin mới.
  - `EpisodeStore`/`MemoryStore` có `_generation` tăng khi `clear()`; kết quả tóm tắt/trích xuất mang thế hệ cũ thì bỏ (`remember()` chụp `store.generation` trước khi gọi model).
  - `resolve_relative_dates`: "thứ X này" ra ngày trước ngày nói thì cộng 7.
  - **Thử thật với qwen3:8b** (server cô lập cổng 8010, bản sao code + `data/` riêng ở thư mục tạm, TTS/STT tắt; server 8000 và `data/` thật không bị đụng):
    - Lỗi 1: buổi "hôm qua" dựng sẵn + tin "thăng chức": tóm tắt chỉ có chuyện mèo Mướp, buổi mới mở đầu đúng bằng tin thăng chức.
    - Lỗi 3: Chủ nhật 15/11 nói "Thứ Bảy này anh đi phỏng vấn ở FPT" → prompt ghi "thứ Bảy ngày 21/11/2026 (sắp tới)"; hỏi lại thì Mira trả lời 21/11.
    - Lỗi 2: gửi tin rồi `DELETE /api/memory` sau 0,4s: log `{"summarized": false, "cleared": true}`, danh sách tóm tắt rỗng.
    - Thấy thêm (chất lượng model, không phải lỗi code): trả lời tin "thăng chức" bằng "Anh về rồi à… sao hôm nay về sớm vậy?" mà không chúc mừng.
  - Lưu ý: nếu task tóm tắt bị hủy trước khi kịp chạy (chỉ khi tắt server) thì `_summarizing` kẹt đến lần khởi động sau; không ảnh hưởng vì trạng thái này chỉ nằm trong RAM.
- Lỗi tìm được (1–3 đã sửa ở trên, 4–5 còn lại):
  1. `main.py` `/api/chat`: khi buổi cũ đến hạn, `schedule_episode_close` tạo task rồi `episodes.record` tin mới ngay sau → tin đầu của buổi mới bị gộp vào bản tóm tắt buổi cũ và bị xóa khỏi buổi mới. Sửa: chụp lượt cần tóm tắt ngay (đồng bộ) trước khi ghi tin mới.
  2. `episodes.py` `close()`: bấm "Quên hết" lúc đang tóm tắt thì bản tóm tắt vẫn được ghi lại (và lượt mới sau khi xóa có thể bị cắt). `remember()` cũng có thể thêm lại điều vừa xóa. Sửa: đếm "thế hệ" tăng khi clear, bỏ kết quả cũ.
  3. `memory.py` `resolve_relative_dates`: "thứ Bảy này" nói vào Chủ nhật thành ngày hôm qua → gắn "(đã diễn ra)" và bị xóa sớm. Sửa: ngày tính ra trước ngày nói thì +7.
  4. Task nền không giữ tham chiếu (`after_text` khi bị ngắt lời, `schedule_episode_close` trong `/api/chat`). **Đã sửa lần 28.**
  5. `web/main.js`: lỗi LLM thì bỏ tin user khỏi lịch sử nhưng bong bóng vẫn hiện; gửi tin/giọng nói lúc Mira còn đang viết chữ bị bỏ qua lặng lẽ (dễ gặp khi lời chào chờ model nạp nguội). **Đã sửa lần 28.**
- Dọn dẹp: ghi JSON nguyên tử lặp ở 3 store; đọc cờ env lặp 5 chỗ; `episodes.record` ghi lại cả file mỗi lượt trên event loop; Ollama tạo `AsyncClient` mới mỗi lần gọi.
- Bước tiếp: lỗi 4–5 đã sửa ở lần 28; còn phần dọn dẹp nếu muốn.
- `CV_Projects_AIML.md` ở gốc repo là file CV cá nhân được chép sang khi chuyển phiên, không thuộc dự án: đừng commit.

### 2026-11-15 (lần 26): chuẩn bị public lên GitHub
- Rà: lịch sử git không có key/token, chưa từng commit `.env`/model/VRM/`data/`; file lớn nhất 1,5MB (three.js). Clone sạch → `uv sync` → 161 test pass.
- Thêm `LICENSE` (MIT), `license = "MIT"` trong pyproject, bảng license thành phần trong README. Lưu ý: `piper-tts` bản mới là **GPL-3.0** (chỉ là gói phụ thuộc, không nằm trong repo); Zipformer **CC-BY-NC-ND** → dùng thương mại phải đổi sang Whisper.
- Gỡ đường dẫn riêng của máy (ổ D, OneDrive, AppData, thư mục người dùng) khỏi tài liệu và spike; bản cũ vẫn còn trong lịch sử git.
- Người dùng chọn "Ẩn email rồi push": viết lại 10 commit sang email noreply GitHub (`git filter-branch`), đặt `user.email` của repo thành noreply. Sao lưu trước khi viết lại: file bundle nằm cạnh thư mục dự án (`Waifu_chat-backup-truoc-doi-email.bundle`), xóa được khi đã yên tâm.
- **Đã public:** https://github.com/sotbatchien123/mira-voice-companion (nhánh `main`, GitHub nhận license MIT). Kiểm tra trên GitHub: mọi commit dùng email noreply, không có `.env`/model/VRM/`data/`.
- Còn (người dùng tự làm trong cài đặt GitHub): hồ sơ công khai vẫn hiện email thật; nên bật "Keep my email addresses private" + "Block command line pushes that expose my email".
- Chạy online cả ngày: app là một người dùng (trí nhớ, presence dùng chung), cần GPU cho LLM. Đề xuất: máy nhà bật 24/7 + Tailscale (HTTPS, chỉ thiết bị của mình). Không mở công khai khi chưa có đăng nhập.

### 2026-11-14 (lần 25): spec 008 giọng theo cảm xúc + spec 009 trí nhớ sâu hơn
- VieNeu v3 Turbo chỉ có `[cười]`, `[thở dài]`, `[hắng giọng]`, không có tham số tốc độ. Đo: cười +0,9s, thở dài +0,5s, STT không nghe ra chữ (là tiếng thật). Mẫu nghe ở `spikes/audio/emotion_out/` (gitignored).
- Test bắt lỗi cũ: tag `[sad]` đến ngay sau dấu chấm làm câu trước bị gán buồn (bộ tách câu chờ 1 ký tự). Sửa: `ParsedChunk.marks` + `SpeechSegmenter.cut()`; test với 3 kiểu chia mảnh (cả câu, từng từ, từng ký tự).
- Spike tóm tắt (qwen3:8b, 9 lần): trung thực ~1,5s; bản đầu bỏ "FPT" và viết "khám mai" → thêm luật giữ tên riêng, viết đủ mốc thời gian; lần 2 đúng 9/9.
- Kiểm chứng thật: 3 tin qua `/api/chat` có giọng: speed đúng theo cảm xúc, câu vui đầu có tiếng cười (2,48s cho "Ôi, thật sự à!"), câu vui sau 15s không cười lại. Lùi buổi đó về tối hôm qua, khởi động lại server, mở trang: tóm tắt bù rồi chào "Anh về rồi à? … anh có đưa Mướp đi khám chưa?". Hộp thoại Trí nhớ hiện đúng. Đã dọn sạch dữ liệu thử (trí nhớ rỗng như trước, presence trả lại bản cũ).
- Test 148 → 161 pass.
- Chưa: người dùng nghe giọng cảm xúc; chưa thử nhánh hẹn giờ tóm tắt 30 phút với server thật (chỉ test offline với 0 phút).

### 2026-11-14 (lần 24): spec 007 từ đánh thức "Mira ơi"
- Đo trước: VieNeu 3 giọng đọc → Zipformer nghe. Chỉ giọng Ngọc Huyền ra đúng "Mira"; còn lại thành "Vera ơi", "Me ra ơi", "Visa ơi", "Mara ơi", "Misa ơi", "Đi ra ơi", "Này mới ra", "Emmira", "Camera". Câu thường ("Chị mai ơi", "Mía…") không bị nghe thành tên.
- Thiết kế: tên chắc chắn nhận luôn; tên dễ nhầm cần "ơi/à/a" sau hoặc "này/ê/chào" trước; "đi ra" chỉ khi có "ơi". Chỉ xét đầu câu. Test 37 ca từ chuỗi đo thật (15/16 câu gọi được nhận, 0 nhận nhầm). Tổng test 140 pass.
- Kiểm chứng trong trình duyệt bằng mic giả lập (phát WAV vào getUserMedia): im 60s → câu TV bị bỏ qua, ô nhập hiện gợi ý; "Mira ơi, hôm nay trời đẹp quá" → trả lời; "Em thích mùa nào nhất?" ngay sau đó không cần tên → trả lời.
- Lỗi bắt được khi thử: lời chào lúc mở trang treo 94s (model nạp nguội khi server vừa khởi động) nên câu TV lọt vì luật "Mira đang trả lời thì không cần tên". Bỏ luật đó; chỉ giữ "Mira đang phát tiếng" + cửa sổ 60s.
- Chưa thử với mic thật/TV thật trong phòng.

### 2026-11-14 (lần 23): xem lại VoiceDeck vừa được sửa
- VoiceDeck (dự án riêng của người dùng, chưa có commit git) vừa được làm lại:
  - Áp dụng Spec Kit; sửa số nói bằng chữ → chữ số; giữ dấu truy vấn YouTube.
  - `ASR_ALIASES` (DU TUYẾT → youtube…); bỏ `audioop`; bỏ đường dẫn cứng ổ D; cổng CDP động. 101/101 test.
  - Còn mở: chế độ tự nghe chưa có từ đánh thức (câu nói thường kích hoạt lệnh).
- Đánh giá cho Mira:
  - **Không lấy** `spoken_numbers_to_digits`: hợp với lệnh, nhưng với chat sẽ đổi "năm nay" → "5 nay", "một con mèo" → "1 con mèo"; model vẫn hiểu số bằng chữ.
  - **Không cần** `ASR_ALIASES`: đo Zipformer trên 8 câu chat có từ tiếng Anh × 2 giọng → Mira, anime, YouTube, game, TikTok, Facebook, iPhone, Marvel đều đúng; chỉ sai "code" → "cốt" và Python với giọng nam (một phần do TTS đọc tiếng Anh).
  - **Đáng cân nhắc:** vấn đề "tự nghe không có từ đánh thức" cũng có ở chế độ Rảnh tay của Mira (TV/người khác nói → Mira trả lời).
- Mira có thể gợi ý ngược lại cho VoiceDeck: chặn bằng Silero VAD trước Zipformer (đo ở Mira: không chặn thì im lặng/tiếng ồn ra "Và", "Đây", "Tôi").

### 2026-11-14 (lần 22): spec 006 Mira chủ động
- **Spike** `spikes/proactive_prompt.py`:
  - Thiếu buổi thì model nói "trưa rồi" lúc 15:00 → `today_line` có buổi.
  - Lộ "ứng dụng" → cấm trong prompt. Hỏi thăm mà chào lại → dặn rõ.
- **Backend:**
  - `app/presence.py`; `/api/proactive`; `reply_stream()` dùng chung cho chat và lời chủ động (lời chủ động không trích trí nhớ).
  - `trim_history` gộp lượt cùng vai và thêm "(anh mở trang)" khi lịch sử bắt đầu bằng Mira (chỉ khi không bị cắt).
  - Health thêm `proactive`.
- **Frontend:** `runMiraTurn()` dùng chung; chào khi mở trang (chỉ chữ nếu chưa được phát âm thanh); hỏi thăm theo `setInterval`, bỏ qua khi bận/tab ẩn.
- **Kiểm chứng thật** (data thử, đã dọn): chào sau 2 ngày vắng, tải lại không chào, đúng 1 lần hỏi thăm.
- **Lỗi bắt được khi chạy thật:**
  - Model sai ngày dù có "N ngày trước" → `resolve_relative_dates` + `event_status` (code tính ngày).
  - Hỏi thăm 2 lần → chỉ hoạt động của người dùng mới cho hỏi thăm lại.
- Test 87 → 103. `.env` đặt `PROACTIVE_CHECKIN_MINUTES=10`; đã xóa `data/presence.json` và trí nhớ thử.

### 2026-11-14 (lần 21): spec 005 Mira sinh động hơn
- `web/lipsync.js`: `mainVowel` (bỏ dấu thanh, giữ â/ă/ơ…; bỏ âm đệm qu/gi/o-u, iê/yê → ê), `syllableVisemes`, `SyllableTracker` (âm lượng tụt rồi vọt = âm tiết mới).
- `web/avatar.js`:
  - Trộn 5 khẩu hình theo âm tiết × độ mở.
  - Gật nhẹ mỗi âm tiết, dáng đầu theo cảm xúc (chia cổ 0,4 / đầu 0,6), nghiêng khi lắng nghe.
  - `?debug=1` → `window.__mira`.
- `web/mic.js` thêm `onSpeechEnd` (không thì tiếng động ngắn bị bỏ làm Mira nghiêng đầu nghe mãi). `main.js` nối chữ đoạn đang đọc + trạng thái nghe.
- **Kiểm chứng trên Mira.vrm + giọng thật:**
  - 24/24 nguyên âm mẫu; nhịp/âm tiết 0,73–1,0 (5/5 đoạn); đủ 5 khẩu hình; góc đầu đổi đúng chiều (ảnh chụp).
- **Bẫy:** khung trình duyệt ẩn → hoạt ảnh dừng; phải mở khung (`show_pane preview`) mới đo được.
- Không có test JS tự động (không Node); kiểm chứng bằng script trong trình duyệt. Test Python vẫn 86/86.

### 2026-11-14 (lần 20): đổi tên + nạp sẵn model
- Đổi tên thành **Mira – 3D Vietnamese Voice Companion**:
  - Đổi ở README, `<title>`, FastAPI title, `pyproject` (`mira-voice-companion`), constitution 1.0.1 (PATCH).
  - Giữ nguyên: thư mục `Waifu_chat`, khóa localStorage `waifu-*` (đổi thì mất lịch sử/cài đặt), các trích dẫn cũ trong spec 001 và nhật ký.
- `ChatLLM.warm_up()`: Ollama gọi `/api/generate` không prompt để nạp model; Claude không làm gì. Server gọi lúc khởi động và mỗi lần `/api/health` (mở trang), chạy nền, không nạp chồng.
- Đo thật sau khi nhả model: không nạp sẵn chữ đầu 4,57s; mở trang → model vào GPU sau 4,1s → chữ đầu 0,61s; health vẫn trả sau 0,09s.
- Test 83 → 86.

### 2026-11-14 (lần 19): spec 004 trí nhớ dài hạn
- **Spike** (`spikes/memory_extract.py`, qwen3:8b):
  - System prompt 364 token; tiếng Việt ~2,1 ký tự/token.
  - Lần 1, cho model tự chọn điều "outdated" để xóa → nó xóa bừa (câu hỏi "thích ăn gì" làm mất tên, tuổi, nghề, mèo) → bỏ.
  - Lần 2, model chỉ gán loại, code tự thay → không mất oan, thay Đà Nẵng→Sài Gòn đúng; sót 1 ý trong câu 2 ý; tính sai ngày → code tự ghi ngày nói.
  - Bản thân mình ghi nhầm 14/11/2026 là thứ Sáu (đúng là thứ Bảy): test bắt được.
- **Làm:**
  - `ChatLLM.stream(history, system)` + `complete(json_mode)` cho Ollama/Claude; `app/memory.py`.
  - Trích xuất chạy song song với TTS sau `text_done`; `GET/DELETE /api/memory`; nút + hộp thoại "Trí nhớ".
  - `trim_history` theo 5000 ký tự.
- **Lỗi phát hiện khi kiểm chứng:**
  - Trình duyệt dùng `main.js` cũ (không có header cache) → thêm `Cache-Control: no-cache` cho file giao diện. Lần đầu sau cập nhật cần tải lại cứng một lần.
  - Nút header bị ngắt chữ → sửa CSS.
- Test 65 → 83. `verify_memory.py` đạt hết; trình duyệt: xem, quên 1 điều, quên hết đều đúng. Dữ liệu thử đã xóa.

### 2026-11-14 (lần 17): học từ VoiceDeck để nhận dạng tốt hơn
- Người dùng thử mic thật: nghe được nhưng nhận dạng còn sai. Tham khảo dự án VoiceDeck của người dùng.
- VoiceDeck dùng Zipformer-30M-RNNT-6000h (tiếng Việt, sherpa-onnx, CPU). Model có sẵn trên máy (ngoài repo); bộ VietSuperSpeech đã bị xóa.
- So trên giọng người thật (FLEURS, 40 câu): **Zipformer WER 9,2% / 0,27s** so với **Whisper 23,2% / 2,68s**. Trên 15 câu VieNeu: 2,9% so với 13%. Số liệu ở `spikes/audio/KET_QUA.md`.
- Người dùng đồng ý → đã làm:
  - `ZipformerSTT` mặc định, `.env` trỏ `ZIPFORMER_DIR` tới model của VoiceDeck.
  - Phát hiện Zipformer cũng bịa 1 từ khi im lặng/ồn → thêm `speech_only` (Silero VAD của faster-whisper).
  - VAD trình duyệt theo VoiceDeck; tắt `noiseSuppression`. Test 60 → 65.
  - Đo: FLEURS WER 8,8% / 0,18s; `verify_stt` 0% / ~30ms; trình duyệt giữ để nói, rảnh tay, ngắt lời đều đúng.
  - Bẫy khi test: mic giả phải tạo luồng mới mỗi lần `getUserMedia` (app dừng track khi tắt mic).

### 2026-11-14 (lần 16): git + spec 003 nghe giọng nói
- `git init` (nhánh `main`), thêm `.claude/settings.local.json` vào `.gitignore`, dò bí mật trước khi commit: không có. Commit đầu `a858d35`.
- Spec 003 (`specs/003-voice-input-stt/`): spec, plan, tasks, contract `stt.md`.
- **Backend:**
  - `faster-whisper`; `app/stt.py` (`SpeechRecognizer`, `WhisperSTT`, `keep_segment` lọc câu bịa theo số đo thật).
  - `POST /api/stt`, health thêm `stt`, nạp sẵn Whisper lúc khởi động, log `kind: stt` (không lưu âm thanh/nội dung).
- **Frontend:**
  - `web/mic_worklet.js`, `web/mic.js` (AudioWorklet 16kHz, pre-roll 0,3s, hết câu sau 0,8s im, tối đa 30s).
  - Nút mic/rảnh tay; ngắt lời Mira. Sửa `sendBtn` lấy theo id (form giờ có 2 nút).
- **Test 47 → 60.**
- **Kiểm chứng thật:**
  - `verify_stt.py` 5/5 ≤ 2s, WER 6%, 0 câu bịa.
  - Trình duyệt với `getUserMedia` giả (phát WAV): giữ để nói, rảnh tay, ngắt lời (dừng 4 mảnh), mic bị chặn → đều đúng.
- **Chưa:** mic thật, giọng người thật, loa ngoài (tiếng vọng).

### 2026-11-14 (lần 15): nạp model VRM thật của Mira
- Người dùng gửi `.vroid` (file dự án, không dùng được) → hướng dẫn xuất VRM. Texture chọn Shrinked để tiết kiệm VRAM.
- Đọc cấu trúc `Mira.vrm`: VRM 1.0, đủ expression (cả `ee/ih/oh/ou`), 54 xương, 53 spring, texture ~59MB. Chép vào `web/models/waifu.vrm`.
- **Kiểm chứng trên trình duyệt:**
  - Nạp tự động, camera canh mặt, tay buông.
  - Hook `VRMExpressionManager.setValue` qua dynamic import: `sad` 0,8, `surprised`, `blink` 1,0, `aa` tối đa 0,74 khi đang nói.
- **Lỗi bắt được khi chạy thật:** qwen3:8b dùng `[concerned]` → hiện ra khung chat. Sửa `app/emotion_tags.py`: thêm alias (concerned/worried→sad, excited→happy…), bỏ mọi tag lạ còn lại.
- `test_phuc_vu_frontend` phụ thuộc việc chưa có `waifu.vrm` → đổi sang đường dẫn chắc chắn không tồn tại.
- Test 46 → 47 pass. `verify_live --voice` 5/5, 0 tag lộ.

### 2026-11-13 (lần 14): đổi giọng sang VieNeu Mỹ Duyên
- Người dùng chọn **Mỹ Duyên**.
- Thăm dò `infer_stream`: mảnh 0,32s, float32 48kHz, audio đầu 0,23s, RTF ~0,45. Mỗi câu tự có ~0,06s lặng đầu và 0,24–0,37s lặng cuối. int8 không nhanh hơn rõ, nạp lâu hơn → giữ fp32.
- Spec 002 bổ sung FR-010..013, SC-005; tasks Phase 7 (T016–T024).
- **Thay đổi:**
  - `vieneu>=3.8` (`.venv` lên 719MB).
  - `app/tts.py`: hợp đồng `stream`, `VieNeuTTS`.
  - `app/main.py`: `Speaker` chạy nền, `iterate_in_thread`, fade-in 10ms, khoảng nghỉ cho Piper, `text_done`.
  - `web/audio_player.js` phát PCM; `web/main.js` cho ngắt lời sau `text_done`; avatar tự cân âm lượng.
  - `.env(.example)` → `TTS_PROVIDER=vieneu`, `VIENEU_VOICE=Mỹ Duyên`.
- **Test 40 → 46**, có bài khóa chéo chứng minh chữ không chờ giọng.
- **Kiểm chứng thật:**
  - `verify_live --voice` 5/5.
  - 100 mảnh / 3 câu không lỗ hổng.
  - Trình duyệt: ngắt lời đúng, lịch sử đúng; miệng mô phỏng trên âm lượng thật mở trung vị 0,32.
  - Piper dự phòng vẫn chạy.

### 2026-11-13 (lần 13): giọng Piper bị chê, thử VieNeu-TTS
- Người dùng nghe Piper: "cứng, nghe già, bị khựng". Muốn giọng nhẹ kiểu anime Nhật và mượt hơn.
- Đo: không có khoảng chờ giữa các đoạn; "khựng" là do các câu dính liền, không có nhịp nghỉ (0–0,05s). Cao độ Piper 234–250 Hz, không thấp.
- Thử **VieNeu-TTS v3 Turbo** (Apache-2.0, CPU/ONNX):
  - Audio đầu 0,21s (stream), RTF 0,37, không tốn VRAM.
  - 11 giọng nữ, đa số Whisper nghe sai 0–12% (Piper 25–38%).
  - Bắt chước giọng từ mẫu 3–8s.
  - Số liệu ở `spikes/audio/KET_QUA.md`, mẫu ở `spikes/audio/out/vieneu/`.
- Chờ người dùng nghe mẫu và chọn giọng trước khi đổi engine.

### 2026-11-13 (lần 12): prompt tạo model 3D cho Mira
- Người dùng xin prompt tạo model 3D. Chỉ trả lời trong chat, không sửa code.
- Đã chốt yêu cầu kỹ thuật cho file `web/models/waifu.vrm` (dựa trên `web/avatar.js`): cần expression `happy/angry/sad/relaxed/surprised`, `blink`, `aa`, đủ humanoid bone (có `head`, `left/rightUpperArm`), lookAt, spring bone.
- Lưu ý đã báo người dùng: model sinh từ AI text/image-to-3D (Meshy, Tripo…) thường **không có blendshape mặt**, nên miệng/chớp mắt/cảm xúc sẽ không chạy. Khuyên: AI vẽ concept art → dựng trong VRoid Studio → xuất VRM.
- Người dùng muốn dùng Tripo Studio (studio.tripo3d.ai). Theo blog của Tripo: Tripo có Auto Rig, nhưng xuất FBX/GLB, **không thấy xuất VRM trực tiếp** và không tạo blendshape mặt. Muốn đưa vào app thì phải qua Blender + add-on VRM (tự tạo shape key `aa`, `blink`, 5 cảm xúc) hoặc Unity + UniVRM.
- Việc tiếp theo vẫn là T020.

### 2026-11-13 (lần 11): spec 002 – giọng nói Piper
- Spec Kit: `specs/002-voice-tts/` gồm spec, plan, research, contract và tasks. `.specify/feature.json` trỏ sang 002.
- **Backend:**
  - Thêm `piper-tts>=1.8`.
  - Thêm `app/speech_text.py` (tách đoạn, lọc emoji), `app/tts.py` (`SpeechEngine`, `PiperTTS`, nạp giọng nền lúc khởi động), `app/turn_log.py`.
  - `app/main.py`: thêm `voice`, event `audio`/`tts_error`; `/api/health` có thêm `voice`.
  - Thêm `scripts/get_voice.py`, mở rộng `scripts/verify_live.py --voice`.
- **Frontend:** thêm `web/audio_player.js`; nút giọng; avatar `setMouthLevel()`. Hệ số miệng chỉnh theo RMS Piper đo được (trung vị 0,17).
- **Test:** 27 → 40, có `tests/conftest.py` mặc định tắt giọng và log vào thư mục tạm.
- **Đo thật:** audio đầu 0,51–0,68s; 0 đoạn đọc emoji/tag; VRAM không tăng ngoài phần của qwen3:8b.
- **Trình duyệt:**
  - AudioContext chạy, các đoạn phát nối tiếp.
  - Gửi tin mới thì dừng audio cũ.
  - Tắt giọng thì không phát, lựa chọn được nhớ.
  - `get_voice.py` tải lại từ đầu, file giống hệt bản cũ.
- Chèn audio ngay trong luồng làm tổng thời gian mỗi lượt dài thêm khoảng 0,1s/đoạn (Piper), chấp nhận được.
- **Chưa:** chưa nghe bằng tai; chưa thấy miệng trên VRM (T013).
- Cache uv khoảng 7,9GB; ổ C còn khoảng 51GB.

### 2026-11-13 (lần 9): đo TTS/STT/LLM
- Script đo trong `spikes/` (chạy bằng `uv run --no-project`, không thêm dependency dự án). Kết quả ở `spikes/audio/KET_QUA.md`.
- **Piper:**
  - `vais1000` chạy rất nhanh và đủ dấu thanh.
  - `25hours_single` mất dấu thanh → loại.
- **Whisper `small`:** CPU khoảng 1,5s/câu, GPU 0,2–0,3s.
- **F5-TTS tiếng Việt:**
  - Chạy được trên RTX 5070 (torch 2.11+cu128): khoảng 1,4s/câu, khoảng 1–1,3GB VRAM.
  - Đọc rõ hơn Piper (WER 8–15% so với 25–38%).
- **LLM:** `qwen3:4b-instruct` dùng 3,1GB VRAM, nhanh, đủ tag. `qwen3:4b` là bản chỉ-suy-nghĩ → đã `ollama rm`.
- **VRAM nền** (Windows, app) khoảng 2GB. `qwen3:8b` cộng F5 không vừa 8GB.
- **Chưa làm:** chưa ai nghe bằng tai các file trong `spikes/audio/out/`; chưa thử giọng thật qua mic; chưa đo riêng VRAM của Whisper GPU.
- **Cache:** torch cu128 (2,6GB) và các model nằm trong cache của uv/HF. Cache uv khi chạy trong app Claude có thể bị Windows chuyển hướng vào thư mục package của app. Dọn bằng `uv cache clean` nếu cần chỗ.

### 2026-11-13 (lần 8): Ollama tự chạy khi đăng nhập
- Người dùng đồng ý. Tạo `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ollama-serve.vbs`, chạy ẩn `ollama serve`. Xóa file này để tắt.
- Đã thử: tắt `ollama serve` cũ, chạy file `.vbs` → Ollama lên sau 2s, chạy độc lập; `/api/health` ok, chat trả lời bình thường. **Chưa thử khởi động lại máy thật.**
- Người dùng hỏi `ollama launch claude`: đó là lệnh của Ollama để mở Claude Code dùng model local. Không liên quan Waifu Chat, và `qwen3:8b` với context 4096 quá nhỏ cho việc này.

### 2026-11-13 (lần 7): bước 0 – dọn nhỏ
- `pyproject.toml`: `anthropic>=2.8`, đã chạy `uv lock`. Bỏ getter `hasModel` trong `web/avatar.js`.
- Thêm `ChatLLM.check()`:
  - Ollama gọi `/api/tags`, coi "qwen3" và "qwen3:latest" là một.
  - Claude chỉ xem có key, không gọi API.
  - `/api/health` trả `ok` + `problem`. `web/main.js` gọi khi mở trang, hiện lỗi trong khung chat nếu chưa sẵn sàng.
- Test 24 → 27, pass hết. Chạy thật:
  - Tắt Ollama thì `/api/health` và trang báo đúng câu lỗi.
  - Bật lại thì hết báo lỗi, chat chạy bình thường.
- App tray Ollama: tắt rồi mở lại vẫn không bật được server. `server.log` trống, app log báo "timeout waiting for Ollama server to be ready". Nghi do đường dẫn thư mục người dùng có dấu cách nhưng chưa chứng minh. `ollama serve` chạy tay thì ổn.

### 2026-11-13 (lần 6): rà soát cuối, xác định lại kế hoạch
- Đo VRAM: `qwen3:8b` chiếm 5,59GB, tổng đang dùng 7,39/8,15GB → kế hoạch audio phải chạy CPU hoặc đổi LLM nhỏ. Viết lại "Việc tiếp theo" theo ràng buộc này.
- Phát hiện: lower bound `anthropic>=1.0` sai, getter `hasModel` không dùng, context Ollama 4096 token. Chưa sửa, chờ người dùng.

### 2026-11-13 (lần 5): kế hoạch TTS sai, rà soát toàn dự án
- Kế hoạch TTS trước đó có nhiều thông tin bịa: repo `mozilla/common_voice_client`, script GPT-SoVITS, "Whisper API của Anthropic", Common Voice VI 100h. Tải Common Voice thất bại cả 2 cách. Đã xóa thư mục `tts_data` (chỉ có script/log sai). Đã chạy `uv sync` để gỡ các gói `datasets`, `librosa`… cài nhầm vào `.venv`.
- Người dùng chốt: TTS và STT đều local, Whisper `small`, muốn giọng riêng. Đã dọn 63,5GB ổ C.
- Rà soát: kiểm chứng thật T017 và nhớ ngữ cảnh. Sửa lại báo cáo phiên 4 cho đúng (T017 trước đó chỉ dựa vào unit test).
- Đã sửa theo kết quả rà soát:
  - `emotion_tags.py`: bỏ dấu cách sau tag, kể cả khi nằm ở mảnh stream kế tiếp. Regex trong `web/main.js` khớp theo.
  - Lỗi Claude chuyển vào `ClaudeLLM`; `friendly_error` không còn nhắc API key cho lỗi bất kỳ. `/api/health` bỏ `hasKey` (constitution I).
  - `OllamaLLM` bắt lỗi mạng giữa stream. `make_llm()` mặc định `ollama`.
  - Persona: luôn xưng "em", không bịa ký ức.
- Test 20 → 24, tất cả pass. Thêm test cho: dấu cách, Ollama chết giữa stream, sai key và thiếu key Claude, lỗi ngoài dự kiến, provider mặc định. SDK `anthropic` 2.x dùng `httpx2`, nên test giả lập Claude phải dùng `httpx2.MockTransport`.

### 2026-11-13 (lần 4): áp dụng Spec Kit, cài Ollama, kiểm chứng thật
- Áp dụng Spec Kit 1.4.0 (constitution v1.0.0, spec/plan/tasks/research/contracts/quickstart). Tất cả task phase 1–3 (US1 MVP) đều đã done. Research chọn qwen3:8b cho GPU 8GB (5.2GB, Q4_K_M quantization).
- Cài Ollama 0.40.16 (Windows native). App tray timeout, dùng `ollama serve` trực tiếp trong background PowerShell. Pull qwen3:8b thành công (5.2GB).
- Test thật với `scripts/verify_live.py --warmup`: **SC-001** 5/5 câu ≤ 2s (warmup 0.5s), **SC-002** 5/5 emotion tags, **SC-003** 0 leaks → MVP ready! Browser test gửi tin + reload lịch sử ok.
- Cập nhật `README.md` (Ollama install notes, ghi chú tray timeout, verify_live.py), `GHI_NHO.md` (trạng thái hiện tại, session log). `specs/001-local-chat-mvp/tasks.md` đánh dấu T004, T014–T018, T023, T024 done. Pytest 20/20 pass.
- Tiếp theo: TTS + lip-sync, STT + VAD, trí nhớ dài hạn, sau đó Hướng 4 (tham khảo dự án mã nguồn mở).

### 2026-11-13 (lần 3): thêm LLM local qua Ollama
- Người dùng muốn không phụ thuộc API, nên thêm `OllamaLLM` + `make_llm()` trong `app/llm.py` và `LLMError` cho thông báo lỗi thân thiện. `get_llm` trong `app/main.py` giờ chọn theo `LLM_PROVIDER`; `/api/health` trả thêm `provider`.
- Thêm `httpx` vào dependencies chính, thêm `tests/test_ollama.py`. Cập nhật `.env.example` (mặc định ollama), tạo `.env`, cập nhật `README.md`.
- Còn dở: người dùng cài Ollama để test thật.

### 2026-11-13 (lần 2) — chuyển sang Python
- Cài Python 3.12 qua uv, tạo `.venv`, viết lại backend bằng FastAPI (`app/`), frontend chuyển sang JS thuần trong `web/`, vendor three.js/three-vrm.
- Đã xóa toàn bộ file Node: `package.json`, `package-lock.json`, `node_modules`, `tsconfig.json`, `vite.config.ts`, `server/`, `src/`, `public/`, `index.html` gốc, `dist/`.
- Thêm `tests/` (pytest). Cập nhật `README.md`, `.gitignore`, `.env.example`, `.claude/launch.json` (chạy uvicorn cổng 8000).

### 2026-11-13
- Tư vấn các hướng làm AI 3D kiểu Grok Ani; người dùng chốt Hướng 1 rồi Hướng 4.
- Dựng MVP bằng Node/Vite/TypeScript (đã thay bằng Python ở phiên sau).
