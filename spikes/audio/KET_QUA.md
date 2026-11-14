# Kết quả đo TTS / STT / LLM (2026-11-13)

Máy: i7-14650HX (16 nhân), RAM 32GB, RTX 5070 Laptop 8GB.
VRAM nền khi chưa nạp model (Windows, trình duyệt…): khoảng **1,9–2,9GB**, dao động theo app đang mở.

Cách chạy lại: xem đầu mỗi file `bench_*.py`. Thư viện chạy trong môi trường tạm `uv run --no-project`,
không đụng dependency của dự án.

## LLM (`spikes/bench_llm.py`, 8 câu × 2 lượt, `think=false`)

| Model | VRAM thêm | Chữ đầu (trung vị) | Trả lời xong (trung vị) | Có tag | Xưng hô sai* | Ghi chú |
|---|---|---|---|---|---|---|
| `qwen3:8b` | +5,2–5,5GB | 0,10–0,17s | 0,6–1,2s | 16/16 | 0/16 | Đang dùng |
| `qwen3:4b-instruct` | +3,1GB | 0,08s | 0,54s | 16/16 | 0/16 | Hay chèn emoji 🎬😊 → cần lọc trước TTS |
| `qwen3:4b` | +3,2GB | — | 5,3s | 8/16 | — | **Loại**: bỏ qua `think=false`, in phần suy nghĩ tiếng Anh ra câu trả lời. Đã xóa |

\* Bộ lọc tự động chỉ bắt "tớ/tao/tôi/cậu" và vài mẫu "mình …", nên vẫn sót (vd "Mình vừa thấy").

## TTS

| Engine | Chạy trên | Audio đầu tiên | RTF | VRAM | Độ rõ (Whisper nghe lại, WER) | License |
|---|---|---|---|---|---|---|
| Piper `vi_VN-vais1000-medium` | CPU | 0,01–0,04s (stream) | ~0,035 | 0 | 25–38% | CC-BY-4.0 |
| Piper `vi_VN-25hours_single-low` | CPU | 0,03s | ~0,027 | 0 | — | Unknown. **Loại**: mất 23/267 phoneme, chủ yếu là dấu thanh |
| F5-TTS `hynt/F5-TTS-Vietnamese-ViVoice` | GPU | ~1,4s/câu (không stream) | 0,44–0,60 | ~0,74GB torch + context ≈ 1–1,3GB | 8–15% | CC-BY-NC-SA-4.0 (phi thương mại) |
| viXTTS | — | — | — | — | — | **Chưa đo**: cần fork TTS cũ, Python 3.10, script chỉ cho Linux; torch cũ không chạy RTX 5070. Còn yếu với câu < 10 từ |

F5-TTS bắt chước giọng từ một file mẫu. Lần đo này dùng giọng Piper làm mẫu, nên chỉ nói lên tốc độ, chưa nói được chất lượng giọng riêng.

File nghe thử nằm trong `spikes/audio/out/`.

## STT: faster-whisper `small` (audio Piper, 2,6–3,7s)

| Thiết bị | Thời gian | WER |
|---|---|---|
| CPU int8 | ~1,45–1,5s | 0–38% |
| GPU float16 | 0,20–0,32s | 0–31% |

WER cao chủ yếu do giọng Piper đọc chưa rõ: cùng Whisper đó nghe F5 chỉ sai 8–15%.
**Chưa đo với giọng người thật qua mic laptop.**

## Ngân sách VRAM (8GB, nền ~2GB → còn ~5,9GB)

| Cấu hình | Tổng ước tính | Vừa không |
|---|---|---|
| `qwen3:8b` + Piper (CPU) + Whisper (CPU) | ~7,5GB | Vừa |
| `qwen3:8b` + F5 (GPU) | ~8,7GB | **Không** |
| `qwen3:4b-instruct` + F5 (GPU) + Whisper (CPU) | ~6,4GB | Vừa |
| `qwen3:4b-instruct` + F5 + Whisper (GPU) | ~7GB+ | Sát giới hạn, VRAM của Whisper GPU chưa đo riêng |

## Độ trễ ước tính từ lúc người dùng ngừng nói tới lúc nghe tiếng (chưa tính VAD chờ im lặng ~0,5–0,8s)

- 8B + Piper + Whisper CPU: 1,5 + ~0,4 (LLM ra câu đầu) + 0,03 ≈ **2s**, giọng Piper.
- 4B-instruct + F5 + Whisper CPU: 1,5 + ~0,3 + 1,4 ≈ **3,2s**, giọng riêng.
- 4B-instruct + F5 + Whisper GPU: 0,3 + ~0,3 + 1,4 ≈ **2s**, giọng riêng, VRAM sát.

## Học từ Open-LLM-VTuber (MIT, Python, Live2D)

- `faster_first_response`: câu đầu được đọc ngay khi gặp dấu phẩy đầu tiên.
- Tách câu (`pysbd` hoặc regex) rồi đưa từng đoạn sang TTS.
- ASR/TTS cắm-rút qua cấu hình. Họ có sẵn `faster_whisper` và `piper_tts`.
- Ngắt lời khi đang nói mà không cần tai nghe (chống tự nghe giọng mình).

## Bẫy cài đặt gặp phải

- PyAV bản mới không khớp faster-whisper (`metadata_errors`). Cách né: tự đọc WAV rồi đưa mảng numpy vào.
- Whisper chạy GPU trên Windows cần `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` và thêm thư mục `nvidia/*/bin` vào đường tìm DLL.
- PyPI có torch 2.15 bản CPU, mới hơn bản cu128 (2.11), nên uv tự chọn nhầm bản CPU. Phải ghim `torch==2.11.0+cu128`.
- torchaudio 2.11 đọc file qua torchcodec, cần DLL FFmpeg. Cách né: đọc WAV bằng `soundfile`.
- Thẻ `qwen3:4b` trên Ollama là bản chỉ-suy-nghĩ. Phải dùng `qwen3:4b-instruct`.

## Bổ sung 2026-11-13: VieNeu-TTS v3 Turbo (sau khi người dùng chê Piper "cứng, già, khựng")

`bench_vieneu.py`, vieneu 3.8.4, CPU fp32 qua ONNX (không torch). License Apache-2.0, 23 giọng có sẵn,
bắt chước giọng từ đoạn mẫu 3–8s, có tag `[cười]`, `[thở dài]` (thử nghiệm), có watermark âm thanh (mặc định bật).

- Nạp lần đầu (gồm tải model): 48,9s. VRAM không đổi.
- Stream: audio đầu **0,21–0,22s**, RTF **0,37**. Tạo cả câu ~4s audio: 1,2–2,3s.
- Giọng nữ (F0 trung vị càng cao thường nghe càng trẻ/nhẹ; WER = Whisper small nghe lại):

| Giọng | Vùng, kiểu | F0 | WER |
|---|---|---|---|
| Đoan Trang | Bắc, tự nhiên | 285 Hz | 12% |
| Thục Đoan | Nam, kể chuyện | 273 Hz | 6% |
| Trúc Ly | Bắc, tự nhiên | 266 Hz | 6% |
| Kim Thanh | Nam, đọc truyện | 250 Hz | 0% |
| Mỹ Duyên | Nam, đọc truyện | 235 Hz | 0% |
| Mai Anh | Bắc, tin tức | 227 Hz | 0% |
| Thùy Dung | Nam, tin tức | 223 Hz | 0% |
| Ngọc Huyền | Bắc, tự nhiên | 216 Hz | 0% |
| Quỳnh Anh | Bắc, đọc truyện | 211 Hz | 0% |
| Ngọc Linh / Ngọc Trân | Bắc / Trung | 197 Hz | 19% |

So sánh: Piper vais1000 F0 234–250 Hz, WER 25–38%. Cao độ của Piper không thấp, nên cảm giác "già" là do âm sắc và
ngữ điệu đều, không phải do giọng trầm.

**"Khựng" với Piper không phải do chờ đoạn sau** (đo 3 câu: thời gian chờ giữa các đoạn = 0). Nguyên nhân: mỗi đoạn chỉ
có 0–0,05s im lặng đầu/cuối nên các câu dính liền, không có nhịp nghỉ; câu ngắn đọc rất nhanh ("Chào anh!" 0,41s).

Mẫu nghe thử: `out/vieneu/<tên giọng>.wav`.

## Bổ sung 2026-11-14: STT trong app (spec 003)

`bench_stt.py` (WhisperSTT của app, small CPU int8, giọng VieNeu 3 người + nhiễu):
- Nhận dạng ~1,5s/câu 1,4–2,4s với luồng mặc định; **12 luồng: 1,25s** (16 luồng không nhanh thêm).
- WER trung bình 13% (Mỹ Duyên/Trúc Ly tốt; giọng nam Thái Sơn tới 43%).
- Không VAD: ồn trắng 0,05 và ù 50Hz đều bị bịa "Hãy subscribe cho kênh Ghiền Mì Gõ" với no_speech_prob 0,89–0,93 nhưng
  avg_logprob -0,28 → bộ lọc phải dựa vào no_speech_prob > 0,8 + danh sách câu bịa, không dựa vào logprob.
  Câu nói thật có no_speech_prob tới 0,58.
- Qua HTTP (`scripts/verify_stt.py`, giọng Ngọc Huyền): 1,23–1,35s, WER trung bình 6%, 0 câu bịa từ im lặng/ồn/ù.

## Bổ sung 2026-11-14: Zipformer-30M (từ dự án VoiceDeck) so với Whisper small

`bench_asr_compare.py`. Zipformer: `hynt/Zipformer-30M-RNNT-6000h` int8 qua sherpa-onnx 8 luồng, model có sẵn ở
`D:\voice_models\Zipformer-30M-RNNT-6000h` (license CC-BY-NC-ND-4.0: chỉ dùng cá nhân). Whisper: `WhisperSTT` của app.

| Bộ dữ liệu | Zipformer WER | Whisper WER | Zipformer trễ | Whisper trễ |
|---|---|---|---|---|
| FLEURS vi_vn test, 40 câu người thật (TB 12,7s/câu)* | **9,2%** | 23,2% | **0,27s** (p95 0,44s) | 2,68s (p95 11,4s) |
| 15 câu VieNeu 3 giọng (không có trong dữ liệu huấn luyện) | **2,9%** | 13% | **0,06s** | ~1,3s |

\* FLEURS nằm trong danh sách dữ liệu huấn luyện của Zipformer (có thể phần train) → con số có thể lạc quan;
bộ VieNeu xác nhận cùng kết luận.

Zipformer ra chữ IN HOA, không dấu câu → cần chuẩn hóa trước khi hiển thị. Nạp 2,4s (Whisper 37,9s lần này).
VoiceDeck còn: VAD năng lượng ngưỡng tối thiểu 0,008, cần ≥ 180ms tiếng nói mới tính, hết câu sau 0,7s im;
ghi âm thô không lọc ồn.
