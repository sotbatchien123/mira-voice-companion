/**
 * Gửi lịch sử chat lên server và đọc Server-Sent Events.
 * @param {{role: "user"|"assistant", content: string}[]} messages
 * @param {{
 *   onText: (t: string) => void,
 *   onEmotion: (e: string) => void,
 *   onAudio?: (a: {seq: number, part: number, rate: number, pcm: string, text?: string, emotion?: string | null}) => void,
 *   onVoiceError?: (message: string | null) => void,
 *   onTextDone?: (raw: string) => void,
 * }} handlers
 * @param {{voice?: boolean, signal?: AbortSignal, url?: string, extra?: object}} [options]
 *   url/extra: dùng cho lời Mira tự nói (/api/proactive, {kind}).
 * @returns {Promise<string | null>} câu trả lời gốc (còn tag) để lưu lịch sử; null nếu server báo chưa đến lúc (204)
 */
export async function streamChat(
  messages,
  { onText, onEmotion, onAudio, onVoiceError, onTextDone },
  { voice = false, signal, url = "/api/chat", extra = {} } = {},
) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...extra, messages, voice }),
    signal,
  });
  if (res.status === 204) return null;
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => null);
    const msg = Array.isArray(detail?.detail) ? detail.detail[0]?.msg : detail?.detail;
    throw new Error(msg ?? `Server trả về ${res.status}`);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === "text") onText(event.text);
      else if (event.type === "emotion") onEmotion(event.emotion);
      else if (event.type === "audio") onAudio?.(event);
      else if (event.type === "tts_error") onVoiceError?.(event.message);
      else if (event.type === "voice_off") onVoiceError?.(null); // engine giọng đang tắt: như lỗi giọng nhưng không báo
      else if (event.type === "text_done") onTextDone?.(event.raw);
      else if (event.type === "error") throw new Error(event.message);
      else if (event.type === "done") return event.raw;
    }
  }
  throw new Error("Kết nối bị ngắt giữa chừng");
}
