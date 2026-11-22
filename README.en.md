Tiếng Việt: [README.md](README.md)

> **Rule:** Read [GHI_NHO.md](GHI_NHO.md) before working on this project, and update it at the end of each session.

# Mira – 3D Vietnamese Voice Companion

Browser-based 3D anime character chatbot: VRM avatar (Three.js + three-vrm), Python backend
(FastAPI), facial expressions driven by emotion tags inserted by the LLM, CPU-based Vietnamese
speech synthesis (VieNeu-TTS, "Mỹ Duyên" voice), and volume-based lip-sync. Supports voice input via mic
(CPU-based Vietnamese Zipformer-30M): push-to-talk, or hands-free with barge-in (interrupting Mira mid-sentence). Mira remembers what you tell her across days
(long-term memory stored locally, viewable/deletable via the **Trí nhớ** (Memory) button). Mira is proactive: she greets you when you return and
checks in once if you've been quiet for a while.
Selectable character "brain": **local model via Ollama** (free, offline) or **Claude API**.
No Node.js required: frontend libraries are pre-vendored in `web/vendor/`.

## Quick Start

Requires [uv](https://docs.astral.sh/uv/) (manages Python 3.12 + project dependencies).

1. `uv sync` (first time: creates `.venv` with Python 3.12 and installs dependencies).
2. Copy `.env.example` to `.env` (defaults to Ollama).
3. Choose the brain:
   - **Ollama (no API key needed):** install Ollama from ollama.com (`winget install Ollama.Ollama`) and open the app. On this machine, the tray app failed to start the server (logs showed "timeout waiting for Ollama server to be ready"), so an `ollama-serve.vbs` file was placed in the Startup folder (`Win+R` → `shell:startup`) to run `ollama serve` hidden on login. Delete that file to disable autostart. On other machines, open a terminal running `ollama serve` and leave it open. Then run `ollama pull qwen3:8b` in another terminal. The web page will warn you immediately on load if Ollama isn't running or the model isn't pulled.
   - **Claude:** set `LLM_PROVIDER=claude` and fill in `ANTHROPIC_API_KEY` in `.env`.
4. Voice: defaults to **VieNeu-TTS v3 Turbo** (Apache-2.0, CPU, uses no VRAM), voice `Mỹ Duyên`. On first run,
   it automatically downloads the model from Hugging Face and loads it (~10s on each server start). Toggle with the **Giọng: bật/tắt** (Voice: on/off) button on the page; your choice is remembered.
   To use Piper (lighter, more robotic voice): `uv sync --extra piper`, set `TTS_PROVIDER=piper`, then run `uv run python scripts/get_voice.py`.
5. Character model: create one with **VRoid Studio** → Export → VRM, then place it at `web/models/waifu.vrm`
   (or drag and drop a `.vrm` file onto the web page).
6. `uv run uvicorn app.main:app --reload --port 8000` → open http://localhost:8000

On Windows: double-click `start.bat` (starts Ollama if needed, runs the server without `--reload`, and opens the browser once it's ready).
Closing that window stops Mira.

After editing `.env`, you must **stop and restart the server**: `--reload` only watches `.py` files.

Tests:
- `uv run pytest` (uses mocked LLM, Ollama, and voice; does not call real models).
- `uv run python scripts/verify_memory.py` (tests memory with a real model; only run when memory is empty, cleans up automatically afterward).
- `uv run python scripts/verify_stt.py` (tests speech recognition against the real server: latency, WER, silence/noise).
- `uv run python scripts/verify_live.py --warmup [--voice]` (live test with real models: measures text and audio latency, emotion tags,
  and checks for leaked or spoken tags/emoji).
- Each chat turn logs one line to `logs/turns.jsonl`: time to first token, first audio, total time, model, and errors. Message content is not logged.
- TTS/STT/LLM benchmarks on this machine: `spikes/audio/KET_QUA.md`.

## Project Structure

| File | Role |
|---|---|
| `app/main.py` | FastAPI: `POST /api/chat` SSE stream, `GET /api/health`, serves `web/` |
| `app/llm.py` | `ClaudeLLM` and `OllamaLLM` sharing the `stream()` contract; `make_llm()` selects via `LLM_PROVIDER` |
| `app/persona.py` | System prompt: character persona + emotion tag conventions |
| `app/emotion_tags.py` | Strips `[happy]`… tags from the text stream (including tags split across two chunks) |
| `app/speech_text.py` | Splits replies into chunks for early speech synthesis (first chunk splits at commas), strips emoji/symbols |
| `app/tts.py` | `SpeechEngine` contract (chunked PCM streaming) + `VieNeuTTS`, `PiperTTS`; `make_tts()` selects via `TTS_PROVIDER` |
| `app/turn_log.py` | Writes `logs/turns.jsonl` |
| `web/avatar.js` | 3D scene, VRM loading, idle animations (breathing, blinking, head sway), expressions, vowel + volume lip-sync, head nods/tilts synced to speech rhythm, emotions, and listening state |
| `web/lipsync.js` | Primary vowel of each Vietnamese syllable → visemes aa/ih/ou/ee/oh; syllable-beat detection from volume |
| `web/audio_player.js` | Plays chunked PCM audio (Web Audio), measures volume for lip-sync, stops when a new message is sent |
| `web/chat_client.js` | Reads SSE from the server |
| `app/memory.py` | Long-term memory: `data/memory.json` store, replace/append rules by category, LLM extraction, builds system prompt with current date/time |
| `app/presence.py` | Proactive Mira: last spoken/greeted timestamps (`data/presence.json`), greeting/check-in timing, hidden prompts for the model |
| `app/stt.py` | `SpeechRecognizer` contract + `ZipformerSTT` (default, with Silero VAD to filter silence) + `WhisperSTT` (fallback) |
| `web/mic.js`, `web/mic_worklet.js` | 16kHz PCM recording, push-to-talk, hands-free mode (energy-based VAD) |
| `web/main.js` | Chat UI, voice/mic/hands-free controls, interrupting Mira, persists history to localStorage |
| `web/vendor/` | three.js 0.187 + three-vrm 3.5.5 (MIT, see `VERSIONS.txt`) |

### `/api/chat` SSE Protocol

Request: `{messages, voice}` (`voice` defaults to `false`).

`{type:"emotion", emotion}` · `{type:"text", text}` (tags stripped) ·
`{type:"audio", seq, part, rate, pcm, text?, emotion?}` (chunked 16-bit PCM base64, only when `voice` is true) ·
`{type:"text_done", raw}` (text finished, audio may still be generating) · `{type:"tts_error", message}` (does not end
the stream) · ends with `{type:"done", raw}` (original reply with tags, saved to history by the client) or `{type:"error", message}`.
Details: `specs/002-voice-tts/contracts/chat-sse.md`.

`POST /api/stt`: 16-bit 16kHz mono PCM body → `{text, audio_ms, ms}` (see `specs/003-voice-input-stt/contracts/stt.md`).

## Configuration (`.env`)

- `LLM_PROVIDER`: `ollama` (default, even without `.env`) or `claude`.
- Ollama:
  - `OLLAMA_MODEL`: default `qwen3:8b`, fits in an 8GB GPU.
  - `OLLAMA_URL`: default `http://127.0.0.1:11434`.
  - `OLLAMA_THINK=false`: disables Qwen 3 thinking mode for speed. Leave empty if the model doesn't support it.
  - `OLLAMA_KEEP_ALIVE`: how long to keep the model in VRAM, default `30m`.
  - `OLLAMA_TEMPERATURE`: default `0.8`.
- Claude:
  - `ANTHROPIC_API_KEY`: API key from console.anthropic.com.
  - `CLAUDE_MODEL`: default `claude-opus-5-5`.
  - `CLAUDE_EFFORT`: `low` (default), `medium`, `high`.
  - *Server-side fallback* is enabled: if the primary model refuses a prompt due to safety filters, the API automatically retries with a fallback model.
- Voice:
  - `TTS_PROVIDER`: `vieneu` (default), `piper`, `voicevox`, or `none`.
  - `VIENEU_VOICE`: default `Mỹ Duyên`; other Vietnamese female voices: Trúc Ly, Thục Đoan, Đoan Trang, Kim Thanh, Mai Anh…
  - `VIENEU_PRECISION`: `fp32` (default) or `int8` (not noticeably faster on this machine).
  - `PIPER_VOICE`: path to `.onnx` file, default `models/piper/vi_VN-vais1000-medium.onnx`.
  - `PIPER_LENGTH_SCALE`: `>1` speaks slower, `<1` speaks faster.
  - When using `TTS_PROVIDER=voicevox` (Japanese voice ずんだもん / Zundamon while chat text shows Vietnamese only; the VOICEVOX app or `run.exe` must be started first, and the credit `VOICEVOX:ずんだもん` is displayed in the app as required by the voice's terms):
    - `VOICEVOX_URL`: default `http://127.0.0.1:50021`.
    - `VOICEVOX_SPEAKER`: default `3` (ずんだもん ノーマル / Zundamon Normal).
    - `VOICEVOX_EMOTION_STYLES`: default `happy:1,angry:7,sad:76` (あまあま / ツンツン / なみだめ).

- Speech recognition:
  - `STT_PROVIDER`: `zipformer` (default), `whisper`, or `none`.
  - `ZIPFORMER_DIR`: Zipformer-30M-RNNT-6000h model directory (CC-BY-NC-ND-4.0, personal use only); default `models/zipformer`,
    download with `uv run python scripts/get_stt_model.py`. If you already have the model elsewhere, point `ZIPFORMER_DIR` to it.
  - When using Whisper:
  - `WHISPER_MODEL` (`small`), `WHISPER_DEVICE` (`cpu`; `cuda` requires cuBLAS/cuDNN + free VRAM), `WHISPER_THREADS` (12).

- Memory: `MEMORY_ENABLED` (`true` by default). Stored in `data/memory.json`, ignored by git.
  - Conversation summaries: after `EPISODE_GAP_MINUTES` (30) minutes of silence, Mira summarizes the session
    (`data/episodes.json`) so she remembers what you talked about next time. View/delete via the **Trí nhớ** (Memory) button.
  - Dated events older than 14 days are automatically pruned from memory.

- Emotion-aware voice (VieNeu only): `VOICE_EMOTION_CUES` (`true`: laughter before happy lines, sigh before sad lines,
  at most once per type within `VOICE_CUE_COOLDOWN_SECONDS` = 120s), `VOICE_EMOTION_SPEED` (`true`: happy lines play
  5% faster/higher, sad lines 6% slower/lower).

- Proactive Mira: `PROACTIVE_GREETING` (`true`), `GREET_MIN_GAP_MINUTES` (30), `PROACTIVE_CHECKIN_MINUTES` (10, 0 = off).

- Hands-free wake word: `HANDSFREE_WAKE_WORD` (`true`), `WAKE_WINDOW_SECONDS` (60). After 60 seconds of silence, you must start
  with `"Mira ơi / Mira à / Này Mira / Ê Mira…"` (Vietnamese calls like "Hey Mira") for Mira to reply; not needed during active conversation or push-to-talk.

- `ALLOWED_HOSTS` (default `localhost,127.0.0.1,[::1]`): the server only accepts requests for these hostnames so untrusted websites
  can't read memory via DNS rebinding. To access from another device (e.g. Tailscale), add its hostname, e.g.
  `localhost,127.0.0.1,may-nha.tail1234.ts.net`.

## Current Limitations

- The opening greeting on page load is text-only if the browser hasn't allowed audio playback yet (no user click on the page).
- The 8B model occasionally adds minor fabricated details when greeting/checking in, even when instructed not to.
- Emotion-aware voice only has 3 VieNeu-supported cues (laugh, sigh, throat clear); changing speed also shifts pitch. During
  laughs/sighs, volume-based lip-sync also moves the mouth. The 8B model occasionally picks odd emotions
  (e.g. `[angry]` for a worried line).
- Conversation summaries are written by the 8B model and sometimes omit small details. If the server shuts down before summarizing, the next greeting
  waits an extra ~1.5s to catch up.
- Wake-word detection matches STT output text, so it accepts a few common misrecognitions (`"Vera ơi"`, `"Misa ơi"`…). Actually starting a sentence with
  `"Visa ơi"` / `"Mara ơi"` will also wake Mira; `"Ê Mira"` is sometimes misheard as `"Camera"` and ignored.

- No custom voice for Mira yet (VieNeu can clone a voice from a 3–8s sample, pending a licensed voice sample).
- Long replies keep the CPU busy generating speech (~0.45s per second of audio).
- Speech recognition measured on real human speech (FLEURS): ~9% WER. Not yet measured on the user's laptop mic after switching to Zipformer. Hands-free mode
  relies on browser echo cancellation; headphones are more reliable.
- After Ollama goes idle (`OLLAMA_KEEP_ALIVE`, default 30 minutes), the model is unloaded from the GPU. The app preloads it in the background on startup
  and on each page load (~4s), so sending a message within the first few seconds is still slower (measured: 4.6s vs 0.6s).
- Long-term memory only stores "memorable facts" extracted by the 8B model: it sometimes misses points in multi-part sentences; wrong entries can be deleted via
  the **Trí nhớ** (Memory) button. History sent to the model is trimmed to ~5000 characters to fit a 4096-token context window.
- Motion is still procedural (breathing, blinking, emotional head poses, rhythmic nods); no arm/torso animations yet.
- Append `?debug=1` to the page URL to expose `window.__mira.avatar` for measurements/debugging.
- Small local models occasionally omit emotion tags or invent tags (e.g. `[concerned]`). Common invented tags are mapped to the closest supported emotion
  (`app/emotion_tags.py`, `ALIASES`), and any remaining unknown tags are stripped so they aren't displayed or read aloud.

## License

Project source code: [MIT](LICENSE).

Models and libraries are **not included in this repo**: they are downloaded locally during setup and are governed by their own licenses.

| Component | Used for | License |
| --- | --- | --- |
| [three.js](https://github.com/mrdoob/three.js) 0.187, [three-vrm](https://github.com/pixiv/three-vrm) 3.5.5 (vendored in `web/vendor/`) | 3D rendering, VRM | MIT |
| [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) v3 Turbo | Text-to-speech (default) | Apache-2.0 |
| [piper-tts](https://github.com/OHF-voice/piper1-gpl) + `vi_VN-vais1000-medium` voice | Text-to-speech (fallback, installed only via `uv sync --extra piper`) | GPL-3.0 (library) / CC-BY-4.0 (voice) |
| VOICEVOX engine + ずんだもん (Zundamon) voice | Japanese text-to-speech (`TTS_PROVIDER=voicevox`; runs separately on the user's machine, not in the repo) | [VOICEVOX terms](https://voicevox.hiroshiba.jp/term/) and [ずんだもん voice terms](https://zunko.jp/con_ongen_kiyaku.html) (credit `"VOICEVOX:ずんだもん"` required; no political/religious use, nothing against public order, no lies/fakes) |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Running Zipformer | Apache-2.0 |
| [Zipformer-30M-RNNT-6000h](https://huggingface.co/hynt/Zipformer-30M-RNNT-6000h) | Speech-to-text (default) | **CC-BY-NC-ND-4.0: non-commercial use only** |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + Whisper `small`, Silero VAD | Speech-to-text (fallback), silence filtering | MIT |
| [Qwen3](https://huggingface.co/Qwen/Qwen3-8B) via [Ollama](https://ollama.com) | Local "brain" (default) | Apache-2.0 / MIT |

For commercial use, switch speech recognition to Whisper (`STT_PROVIDER=whisper`), since Zipformer's license
does not permit commercial use. The VRM character model is user-supplied and not included in this repo.
