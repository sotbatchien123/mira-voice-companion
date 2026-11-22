# Spec 011: Chat tiếng Việt, giọng tiếng Nhật (VOICEVOX ずんだもん)

Trạng thái: người dùng đã duyệt (2026-11-21).

## Ý định

Người dùng vẫn chat với Mira bằng tiếng Việt (gõ hoặc nói), chữ Mira trả lời hiện bằng tiếng Việt như bây giờ, nhưng
**giọng Mira phát ra là tiếng Nhật**, đọc bản tiếng Nhật của câu trả lời bằng giọng VOICEVOX ずんだもん. Lý do: người
dùng thích chất giọng Nhật kiểu anime (không phải để học tiếng Nhật), nên bản dịch chỉ cần tự nhiên, không cần hiện ra.

Người dùng đã chọn: engine **VOICEVOX**, giọng **ずんだもん**, câu tiếng Nhật do **chính model viết kèm** (không gọi dịch
riêng).

## Mục tiêu

1. Bật bằng `.env`: `TTS_PROVIDER=voicevox`. Mặc định vẫn là VieNeu tiếng Việt; tắt VOICEVOX thì mọi thứ như cũ.
2. Khi bật, model viết mỗi câu tiếng Việt kèm bản tiếng Nhật trong thẻ: `[happy] Anh về rồi hả! <ja>おかえり！</ja>`.
3. Màn hình, lịch sử hiển thị, trí nhớ, buổi trò chuyện chỉ thấy tiếng Việt (không lộ `<ja>` hay chữ Nhật).
4. Giọng đọc chỉ nhận phần trong `<ja>…</ja>`, đọc bằng ずんだもん, câu đầu có giọng sớm như bây giờ (đọc từng câu khi
   thẻ `</ja>` đóng, không chờ hết câu trả lời).
5. Cảm xúc đổi sắc thái giọng: dùng style của ずんだもん (ノーマル 3, あまあま 1, ツンツン 7, なみだめ 76, ささやき 22),
   ví dụ happy → あまあま, angry → ツンツン, sad → なみだめ; cấu hình được.
6. Nhép môi theo tiếng Nhật: dùng nguyên âm từng âm tiết (mora) mà `audio_query` của VOICEVOX trả về
   (`a i u e o`, `N` = ngậm miệng), thay cho cách đoán nguyên âm tiếng Việt.
7. Ghi nguồn đúng điều khoản: "VOICEVOX:ずんだもん" hiện ở chỗ dễ tìm trong giao diện khi đang dùng giọng này, và trong
   README.
8. VOICEVOX chưa chạy thì `/api/health` báo câu tiếng Việt dễ hiểu (như các engine khác), chat chữ vẫn chạy.

## Không làm (lần này)

- Nghe tiếng Nhật (STT vẫn tiếng Việt). Hiện chữ tiếng Nhật trên màn hình. Dịch lại lịch sử cũ.
- Nhân bản giọng Amitaro. Đưa VOICEVOX vào repo hay tự cài nó (người dùng tự tải; engine cấm phân phối lại).
- Tự bật VOICEVOX trong `start.bat` (có thể làm sau).
- `[cười]`/`[thở dài]` (chỉ VieNeu hiểu); tốc độ theo cảm xúc ở trình duyệt vẫn giữ.

## Phản mục tiêu (làm xong mà dính những điều này là hỏng)

- Chữ Nhật hoặc thẻ `<ja>` lọt ra bong bóng chat, trí nhớ, tóm tắt buổi, hoặc bị VieNeu đọc khi tắt VOICEVOX.
- Tính cách / cách xưng hô tiếng Việt của Mira tệ đi vì prompt thêm phần tiếng Nhật.
- Chữ tiếng Việt hiện chậm hơn quá ~2 lần so với hiện tại, hoặc câu đầu có giọng chậm hơn hẳn (đo, so với VieNeu).
- Câu tiếng Việt bị đọc bằng giọng Nhật (đọc sai, nghe vô nghĩa).

## Ràng buộc

- GPU 8GB chỉ chạy một LLM (`qwen3:8b`); không thêm lượt gọi model cho việc dịch.
- VOICEVOX engine chạy riêng (`run.exe`, CPU) ở `VOICEVOX_URL` (mặc định `http://127.0.0.1:50021`), ngoài repo. Đường dẫn
  máy người dùng không vào git (lưu ý `.claude/launch.json` đang có cấu hình `voicevox` với đường dẫn riêng).
- Điều khoản ずんだもん (zunko.jp/con_ongen_kiyaku.html, đọc 2026-11-21): thương mại/phi thương mại đều được nếu ghi
  "VOICEVOX:ずんだもん" ở chỗ dễ tìm trong app; cấm chính trị, tôn giáo, trái thuần phong mỹ tục, nói dối/làm giả,
  quảng cáo "thông tin kiếm tiền". Không nhắc tới chatbot AI hay dùng giọng cho nhân vật khác tên. Điều khoản chung
  VOICEVOX: cấm phân phối lại engine.
- Persona hiện cấm markdown/emoji vì câu được đọc thành tiếng; thẻ `<ja>` là ngoại lệ có chủ đích.

## Các hướng đã cân nhắc

1. **Model viết kèm `<ja>` (đã chọn).** Một lượt gọi model, giọng đến sớm. Đổi lại: chữ Việt hiện chậm hơn (model viết
   thêm tiếng Nhật), model 8B có lúc quên thẻ → câu đó im.
2. Dịch sau khi viết xong: chữ Việt nhanh như cũ, bản dịch ổn định hơn, nhưng giọng chỉ bắt đầu sau cả câu trả lời +
   một lượt dịch (thêm ~1–3 giây vì GPU xếp hàng). Người dùng không chọn.
3. Engine giọng khác (Kokoro: Apache-2.0 nhưng tiếng Nhật chất lượng thấp; AivisSpeech/Style-Bert-VITS2: nặng, tranh
   GPU, license từng model chưa kiểm). Người dùng chọn VOICEVOX sau khi nghe mẫu.

## Thiết kế

**Prompt.** Khi engine giọng là tiếng Nhật, `system_prompt` thêm một đoạn: sau mỗi câu tiếng Việt, viết bản tiếng Nhật tự
nhiên, giọng nói chuyện thân mật, trong `<ja>…</ja>`; tag cảm xúc đặt trước câu tiếng Việt như cũ; không giải thích bản
dịch. Kèm 1 ví dụ. Engine báo ngôn ngữ của mình (vd thuộc tính `speech_language = "ja"`), server không hard-code theo tên.

**Tách thẻ trong luồng stream.** Một parser có trạng thái chạy cạnh `EmotionTagParser`: tách mỗi mảnh stream thành
(1) chữ hiển thị = phần ngoài `<ja>…</ja>` và (2) các đoạn tiếng Nhật đã đóng thẻ. Phải chịu được: thẻ bị cắt giữa hai
mảnh (`<j` + `a>`), chữ Nhật dài trải qua nhiều mảnh, thiếu `</ja>` lúc kết thúc (flush: bỏ phần dở hoặc vẫn đọc — builder
chọn, ghi lý do), thẻ lạ/hỏng không được làm mất chữ Việt. Tag cảm xúc ở chữ Việt vẫn quyết định cảm xúc của đoạn Nhật
theo sau. `raw` gửi về trình duyệt (lưu lịch sử, gửi lại cho model) giữ nguyên cả thẻ để model thấy mẫu nhất quán; trình
duyệt bỏ `<ja>…</ja>` khi hiển thị lại lịch sử. `parse_complete(raw).text` (dùng cho buổi trò chuyện) phải bỏ cả phần Nhật.
Trí nhớ chỉ đọc tin của người dùng nên không bị ảnh hưởng.

**Engine `VoicevoxTTS`** theo hợp đồng `SpeechEngine` trong `app/tts.py`: `stream(text)` gọi `POST /audio_query` rồi
`POST /synthesis` (WAV 24kHz mono) và trả PCM 16-bit; `check()` gọi `GET /version`, lỗi thì trả câu tiếng Việt hướng dẫn
mở VOICEVOX; `warm_up()` tổng hợp một câu ngắn. Cấu hình: `VOICEVOX_URL`, `VOICEVOX_SPEAKER` (style id, mặc định 3),
`VOICEVOX_EMOTION_STYLES` (map cảm xúc → style id, mặc định như mục tiêu 5). Cần truyền cảm xúc của đoạn vào engine
(hiện `stream()` chỉ nhận chữ) — builder chọn cách gọn nhất hợp hợp đồng hiện có.

**Nhép môi.** Sự kiện `audio` mảnh đầu của mỗi đoạn kèm thêm chuỗi nguyên âm mora từ `audio_query` (vd
`"ooaooaclaucloa…"`), trình duyệt dùng nó thay cho `syllableVisemes(text)` khi có; `SyllableTracker` vẫn bắt nhịp theo
âm lượng như cũ. `text` của sự kiện vẫn có để hiển thị/ghi log.

**Ghi nguồn.** `/api/health` trả kèm dòng credit của engine (vd `"VOICEVOX:ずんだもん"`), giao diện hiện dòng nhỏ đó (vd cạnh
nút Giọng, hoặc trong hộp thông tin) khi đang dùng giọng này. README thêm VOICEVOX vào bảng license và phần cấu hình.

**Đo khi xong (với qwen3:8b thật).** Tỉ lệ câu có `<ja>` đúng trên ~20 câu trả lời; thời gian chữ đầu và giọng đầu so với
VieNeu; người dùng nghe và đánh giá bản tiếng Nhật có tự nhiên không; không câu nào lộ chữ Nhật/thẻ ra màn hình.

## Quyết định sau khi soát thiết kế (Claude tự quyết, người dùng xem lại)

- **Chữ Nhật lọt ngoài thẻ** (`（おかえり）`, `<JA>`, `<jp>`, dòng tiếng Nhật trơn): bỏ khỏi chữ hiển thị mọi đoạn có
  kana/kanji nằm ngoài `<ja>…</ja>` (tiếng Việt không dùng kana/kanji nên không mất chữ Việt), và **không đọc** chúng.
  Chấp nhận `<JA>`/`<jp>` như `<ja>` cho đỡ phí câu.
- **Prompt `<ja>` theo từng request:** chỉ thêm khi engine là tiếng Nhật **và** request bật giọng (`voice: true`). Tắt
  giọng thì không tốn thêm thời gian viết tiếng Nhật.
- **Ngân sách ngữ cảnh 4096 token:** server bỏ `<ja>…</ja>` khỏi mọi lượt cũ trước khi gửi model (ví dụ trong prompt đủ
  để giữ đúng mẫu), nên ngân sách lịch sử 5000 ký tự vẫn đúng. Trình duyệt vẫn lưu `raw` đủ thẻ. Khi viết kèm tiếng Nhật,
  nâng `num_predict` 512 → 1024 (không tốn thêm VRAM; ngữ cảnh vẫn 4096) để câu trả lời không bị cắt.
- **Nếu chậm (người dùng chọn):** mốc là giọng đầu ≤ 2,5 giây sau khi gửi tin (model đã nạp sẵn). Vượt mốc thì chỉnh
  prompt cho bản Nhật ngắn hơn, đo lại, rồi báo người dùng số liệu; vẫn chậm thì người dùng quyết tiếp (không tự đổi
  sang dịch sau).
- **`.claude/launch.json`:** cấu hình `voicevox` có đường dẫn riêng của máy → không commit phần đó; GHI_NHO ghi cách bật
  VOICEVOX trên máy này.

## Để builder tự quyết

Tên module/hàm, cách truyền cảm xúc và chuỗi nguyên âm qua `Speaker`, xử lý thiếu `</ja>` lúc kết thúc, vị trí chính xác
của dòng credit trên giao diện, chia nhỏ câu Nhật dài thành đoạn (dấu `。！？`), có dùng tham số `speedScale` của VOICEVOX
hay không.
