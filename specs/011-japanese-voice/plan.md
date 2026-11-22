# Japanese Voice (VOICEVOX ずんだもん) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat stays Vietnamese on screen; when `TTS_PROVIDER=voicevox` and voice is on, Mira speaks the Japanese version of each sentence with VOICEVOX ずんだもん.

**Architecture:** The model writes `<ja>…</ja>` after each Vietnamese sentence. A new stream parser (`app/ja_tags.py`) splits model output into display text (fed to the existing emotion parser and the browser) and closed Japanese segments (fed to the `Speaker`). A new `VoicevoxTTS` engine calls the local VOICEVOX HTTP API, picks a ずんだもん style per emotion, and returns PCM plus the mora vowel string used for lip-sync.

**Tech Stack:** FastAPI, httpx (already a dependency), VOICEVOX engine 0.26.2 at `http://127.0.0.1:50021`, vanilla JS.

**Spec:** `specs/011-japanese-voice/spec.md`

## Global Constraints

- Default stays VieNeu Vietnamese; with `TTS_PROVIDER` not `voicevox`, behaviour and prompts are unchanged (all 175 existing tests stay green).
- No extra LLM call for translation. GPU budget: one model (`qwen3:8b`), context 4096.
- Config names: `VOICEVOX_URL` (default `http://127.0.0.1:50021`), `VOICEVOX_SPEAKER` (default `3`), `VOICEVOX_EMOTION_STYLES` (default `happy:1,angry:7,sad:76`, other emotions use `VOICEVOX_SPEAKER`).
- Credit text exactly `VOICEVOX:ずんだもん`, visible in the UI while this voice is in use, and in README.
- No machine paths in git: do not commit the `voicevox` entry of `.claude/launch.json`.
- Slow path (user decision): target first audio ≤ 2.5 s after sending (model warm). If exceeded, shorten the Japanese via the prompt, re-measure, report numbers to the user; do not switch to "translate after".
- Ponytail: smallest complete change; Vietnamese comments/messages like the rest of the codebase.

## Review Focus

1. Japanese with no tag at all (`（おかえり）`, a line of kana) → hidden from the bubble, not spoken. Test in Task 1.
2. `<ja>` split across stream chunks at every position (`<`, `<j`, `<ja`, `</j`…) → no tag text leaks, Japanese segment intact. Test in Task 1.
3. Reply ends with an unclosed `<ja>おかえ` → nothing Japanese in display; the partial segment is spoken (it is real text the model meant to say). Test in Task 1.
4. VOICEVOX not running while `TTS_PROVIDER=voicevox` → `/api/health` voice problem in Vietnamese, chat text still streams, `tts_error` event once. Test in Task 2 / Task 3.
5. Browser history from before this feature or after switching engines (turns with and without `<ja>`) → displays only Vietnamese; server strips `<ja>` from every old turn before sending to the model. Test in Task 3 (server) and checked in browser in Task 4.

---

### Task 1: `<ja>` stream parser

**Files:**
- Create: `app/ja_tags.py`
- Test: `tests/test_ja_tags.py`

**Interfaces:**
- Produces: `JaTagParser().push(chunk: str) -> JaChunk`, `.flush() -> JaChunk`; `JaChunk(display: str, ja: list[str])`; `strip_ja(text: str) -> str` (remove `<ja>…</ja>` incl. `<JA>`/`<jp>`, unclosed tail, and any run of kana/kanji/Japanese punctuation outside tags; collapse doubled spaces).

- [ ] **Step 1: Write failing tests** in `tests/test_ja_tags.py`:
  - `test_tach_cau_viet_va_nhat`: push `"[happy] Anh về rồi hả! <ja>おかえり！</ja> Kể em nghe đi. <ja>聞かせて。</ja>"` → joined display `"[happy] Anh về rồi hả! Kể em nghe đi."`, ja `["おかえり！", "聞かせて。"]`.
  - `test_the_bi_cat_moi_vi_tri`: same input pushed in every 2-way split (loop over all split points) → identical display/ja to the unsplit case.
  - `test_thieu_the_dong_luc_ket_thuc`: `"Chào anh. <ja>おかえ"` then `flush()` → display `"Chào anh."`, ja `["おかえ"]`.
  - `test_chu_nhat_ngoai_the_bi_an`: `"Chào anh (おかえり) nha."` → display `"Chào anh nha."`, ja `[]`.
  - `test_the_viet_sai_kieu`: `<JA>`/`<jp>` treated like `<ja>`.
  - `test_strip_ja`: `strip_ja("[happy] Dạ! <ja>はい！</ja> Vâng.") == "[happy] Dạ! Vâng."`; text without tags unchanged.
- [ ] **Step 2: Run** `uv run pytest tests/test_ja_tags.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `app/ja_tags.py`. Hold back any tail that could still become a tag (`<` … up to 5 chars) like `EmotionTagParser` does; Japanese = `[\u3040-\u30ff\u3400-\u9fff\uff01-\uff5e\u3000-\u303f]`.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `git add app/ja_tags.py tests/test_ja_tags.py` — "Spec 011: tách thẻ <ja> khỏi luồng chữ".

### Task 2: `VoicevoxTTS` engine

**Files:**
- Modify: `app/tts.py` (new class, `make_tts` branch)
- Test: `tests/test_voicevox.py`

**Interfaces:**
- Consumes: `app.util.env_number`, httpx.
- Produces: `VoicevoxTTS(transport: httpx.BaseTransport | None = None)` with `name = "voicevox"`, `speech_language = "ja"`, `credit = "VOICEVOX:ずんだもん"`, `sample_rate = 24000`, `segment_pause_s = 0.0`, `check() -> str | None`, `warm_up() -> None`, `synthesize(text: str, emotion: str | None = None) -> tuple[bytes, str]` (PCM16 mono, mora vowels: one char per mora, `a i u e o`, `N`→`n`, `cl`/pause → `-`), `stream(text) -> Iterator[bytes]` (yields `synthesize(text)[0]`). `make_tts()` returns it for `TTS_PROVIDER=voicevox`.

- [ ] **Step 1: Write failing tests** with `httpx.MockTransport` (no real engine):
  - `test_voicevox_tong_hop_va_nguyen_am`: mock `/audio_query` (returns accent_phrases with moras vowels `o,a,e,N`) and `/synthesis` (a 24 kHz WAV of 100 samples) → `synthesize("おかえり", "happy")` returns 200 bytes PCM and `"oaen"`; the synthesis request used `speaker=1` (happy → あまあま).
  - `test_voicevox_cam_xuc_mac_dinh`: emotion `None`/`"relaxed"` → `speaker=3`; `VOICEVOX_EMOTION_STYLES="sad:76"` → sad uses 76.
  - `test_voicevox_chua_bat`: transport raising `httpx.ConnectError` → `check()` contains `"VOICEVOX"` and `"127.0.0.1:50021"`; `synthesize` raises `TTSError`.
  - `test_chon_engine_voicevox`: `TTS_PROVIDER=voicevox` → `isinstance(make_tts(), VoicevoxTTS)`.
- [ ] **Step 2: Run** `uv run pytest tests/test_voicevox.py -q` → FAIL.
- [ ] **Step 3: Implement** in `app/tts.py`; WAV → PCM via stdlib `wave` + `io.BytesIO`; timeouts short connect (3 s), read 30 s.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** — "Spec 011: engine giọng VOICEVOX".

### Task 3: Wire into the chat flow (prompt, stream, Speaker, history, health)

**Files:**
- Modify: `app/memory.py` (`system_prompt` + `JA_VOICE_PROMPT`), `app/main.py` (`trim_history`, `build_system`, `reply_stream`, `Speaker`, `chat`, `proactive`, `health`), `app/llm.py` (`stream(..., max_tokens: int | None = None)` on both LLMs; Ollama `num_predict`, Claude `max_tokens` use it when given)
- Test: `tests/test_ja_voice_api.py`

**Interfaces:**
- Consumes: Task 1 `JaTagParser`, `strip_ja`; Task 2 `VoicevoxTTS.synthesize`, `.speech_language`, `.credit`.
- Produces: `system_prompt(now, facts, episodes="", speak_ja=False)`; SSE `audio` part-0 event gains `"vowels": str` when the engine is Japanese; `/api/health` `voice` gains `"credit": str | None`.

Rules: ja mode = `req.voice and tts is not None and getattr(tts, "speech_language", "vi") == "ja"`. In ja mode the prompt gets `JA_VOICE_PROMPT` (one example: `[happy] Anh về rồi hả! <ja>おかえり！</ja>`), the LLM gets `max_tokens=1024`, `reply_stream` runs `JaTagParser` before `EmotionTagParser`, the `Speaker` receives only Japanese segments (emotion = latest emotion seen) and calls `synthesize` in a thread. `trim_history` always applies `strip_ja` to assistant turns. `after_reply` records `parse_complete(strip_ja(raw)).text`. `done`/`text_done` `raw` keeps the tags.

- [ ] **Step 1: Write failing tests** (FakeLLM yields `"[happy] Anh về rồi hả! <ja>おかえ"` + `"り！</ja>"`, FakeJaTTS with `speech_language="ja"`, `credit="X"`, `synthesize` returning `(b"\0\0"*10, "oaei")`):
  - `test_che_do_nhat_chi_doc_tieng_nhat`: `/api/chat` voice=true → `text` events joined == `"Anh về rồi hả!"`, one `audio` part 0 with `text == "おかえり！"`, `vowels == "oaei"`, `emotion == "happy"`; `done.raw` contains `<ja>`; FakeLLM saw `max_tokens == 1024` and system containing `<ja>`.
  - `test_tat_giong_khong_them_prompt_nhat`: voice=false → system has no `<ja>`, `max_tokens is None`.
  - `test_lich_su_cu_bo_tieng_nhat`: history assistant turn `"Dạ! <ja>はい！</ja>"` → model received `"Dạ!"`.
  - `test_buoi_tro_chuyen_khong_co_tieng_nhat`: with an `EpisodeStore`, recorded assistant turn has no kana and no `<ja>`.
  - `test_health_co_credit`: health voice has `credit == "X"`; for VieNeu fake `credit is None`.
  - `test_voicevox_loi_van_co_chu`: `synthesize` raises `TTSError` → text still streams, exactly one `tts_error` event.
- [ ] **Step 2: Run** `uv run pytest tests/test_ja_voice_api.py -q` → FAIL.
- [ ] **Step 3: Implement** as in Rules above; keep the Vietnamese path byte-for-byte the same (existing tests prove it).
- [ ] **Step 4: Run** `uv run pytest -q` → all pass (175 + new).
- [ ] **Step 5: Commit** — "Spec 011: Mira đọc bản tiếng Nhật khi dùng VOICEVOX".

### Task 4: Browser (history display, lip-sync from vowels, credit)

**Files:**
- Modify: `web/main.js` (strip `<ja>…</ja>` and kana/kanji when showing saved history; pass `vowels` through `onSegmentStart`; show credit), `web/audio_player.js` (keep `vowels` in part-0 meta), `web/avatar.js` (`setSpeechText(text, vowels)`), `web/lipsync.js` (`moraVisemes(vowels: string) -> string[]`: `a→aa i→ih u→ou e→ee o→oh`, `n`/`-` → closed-mouth entry handled by setting mouth to 0 for that syllable), `web/index.html` (small credit element next to the voice button, hidden when `credit` is null)

- [ ] **Step 1: Implement** the above; credit text comes from `/api/health` `voice.credit`.
- [ ] **Step 2: Verify in browser** with preview `waifu-test` (port 8001, greeting and memory off) and a mocked `/api/chat` stream that sends `text`, `audio` part 0 with `vowels: "oaeioa"`, then `done` whose `raw` contains `<ja>`: bubble shows only Vietnamese; after reload the history bubble shows only Vietnamese; `window.__mira.avatar.visemes` equals `moraVisemes("oaeioa")`; credit element shows `VOICEVOX:ずんだもん` when health says so; console has no errors. Close the test tab afterwards.
- [ ] **Step 3: Commit** — "Spec 011: giao diện cho giọng tiếng Nhật".

### Task 5: Real-model measurement, docs

**Files:**
- Create: `scripts/verify_ja_voice.py` (sends ~20 varied Vietnamese messages to a running server with `voice: true`, counts replies where every Vietnamese sentence got a `<ja>` segment, prints first-text and first-audio ms per reply from the SSE stream, and flags any kana in display text)
- Modify: `README.md`, `README.en.md` (config + license table row: VOICEVOX engine, ずんだもん terms link `https://zunko.jp/con_ongen_kiyaku.html`, credit), `.env.example` (`TTS_PROVIDER` comment + three `VOICEVOX_*` vars), `GHI_NHO.md` (session entry, how to start VOICEVOX on this machine, without the machine's absolute path)

- [ ] **Step 1:** Start VOICEVOX (preview `voicevox`) and Mira with `TTS_PROVIDER=voicevox` on a test port with memory off; run the script; record tag rate, median first-text and first-audio ms; compare with the same messages on VieNeu.
- [ ] **Step 2:** If median first audio > 2.5 s: shorten Japanese in `JA_VOICE_PROMPT` (e.g. "bản tiếng Nhật ngắn gọn"), re-run, report both runs to the user. Send 3 sample replies' audio to the user to judge naturalness.
- [ ] **Step 3:** Update docs; `uv run pytest -q` → all pass.
- [ ] **Step 4: Commit** (excluding `.claude/launch.json` voicevox entry and `CV_Projects_AIML.md`) — "Spec 011: đo với model thật, tài liệu".
