/**
 * Ghi âm mic thành PCM 16-bit 16kHz cho /api/stt.
 * - Bấm giữ: startManual() / stopManual().
 * - Rảnh tay: setHandsFree(true) -> VAD theo năng lượng tự phát hiện đầu/cuối câu.
 */
const RATE = 16000;
const PRE_ROLL_S = 0.3; // giữ lại một chút trước lúc phát hiện tiếng nói để không mất âm đầu
// VAD theo dự án VoiceDeck (chạy ổn với tai nghe Bluetooth): ngưỡng tối thiểu 0.008, nền nhiễu x3,
// cần >= 0.18s tiếng nói mới tính là bắt đầu (bỏ qua tiếng gõ phím, tiếng cạch), im 0.7s là hết câu
const END_SILENCE_S = 0.7;
const MIN_THRESHOLD = 0.008;
const START_SPEECH_S = 0.18;
const MIN_SPEECH_S = 0.3;
const MAX_SPEECH_S = 30;

export class MicError extends Error {}

export class MicRecorder {
  /**
   * @param {{
   *   onUtterance: (pcm: ArrayBuffer, seconds: number) => void,
   *   onSpeechStart?: () => void,
   *   isAssistantSpeaking?: () => boolean,
   * }} handlers
   */
  constructor({ onUtterance, onSpeechStart, isAssistantSpeaking }) {
    this.onUtterance = onUtterance;
    this.onSpeechStart = onSpeechStart ?? (() => {});
    this.isAssistantSpeaking = isAssistantSpeaking ?? (() => false);
    this.ctx = null;
    this.stream = null;
    this.handsFree = false;
    this.manual = false;
    this.chunks = [];
    this.preRoll = [];
    this.inSpeech = false;
    this.loudSeconds = 0;
    this.silence = 0;
    this.noiseFloor = 0.002;
  }

  get open() {
    return this.ctx !== null;
  }

  /** Xin quyền mic và bắt đầu nhận khung âm thanh. Gọi trong cú bấm của người dùng. */
  async start() {
    if (this.ctx) {
      if (this.ctx.state === "suspended") await this.ctx.resume();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) throw new MicError("Trình duyệt này không hỗ trợ mic.");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        // khử tiếng vọng để mic không thu lại giọng Mira từ loa
        // không bật lọc ồn: nó làm méo giọng, còn Zipformer được huấn luyện với dữ liệu có nhiễu (VoiceDeck cũng ghi thô)
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: true },
      });
    } catch (err) {
      throw new MicError(
        err?.name === "NotAllowedError"
          ? "Trình duyệt đang chặn mic. Bấm biểu tượng ổ khóa cạnh địa chỉ trang để cho phép mic rồi thử lại."
          : `Không mở được mic: ${err?.message ?? err}`,
      );
    }
    this.ctx = new AudioContext({ sampleRate: RATE });
    if (this.ctx.state === "suspended") await this.ctx.resume(); // bị tạm dừng thì worklet không chạy
    await this.ctx.audioWorklet.addModule("/mic_worklet.js");
    const src = this.ctx.createMediaStreamSource(this.stream);
    const node = new AudioWorkletNode(this.ctx, "mic-capture");
    node.port.onmessage = (e) => this.onFrame(e.data);
    // Nút worklet phải nối ra loa thì mới được chạy; gain 0 để không phát lại tiếng mic
    const mute = this.ctx.createGain();
    mute.gain.value = 0;
    src.connect(node).connect(mute).connect(this.ctx.destination);
  }

  /** Tắt hẳn mic (đèn mic của trình duyệt tắt). */
  stop() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.ctx = null;
    this.stream = null;
    this.reset();
  }

  setHandsFree(on) {
    this.handsFree = on;
    this.reset();
  }

  startManual() {
    this.manual = true;
    this.chunks = [...this.preRoll];
    this.onSpeechStart();
  }

  stopManual() {
    if (!this.manual) return;
    this.manual = false;
    this.finish();
  }

  reset() {
    this.manual = false;
    this.inSpeech = false;
    this.chunks = [];
    this.loudSeconds = 0;
    this.silence = 0;
  }

  onFrame(frame) {
    const dur = frame.length / this.ctx.sampleRate;
    let sum = 0;
    for (const s of frame) sum += s * s;
    const rms = Math.sqrt(sum / frame.length);

    this.preRoll.push(frame);
    while (this.preRoll.length * dur > PRE_ROLL_S) this.preRoll.shift();

    if (this.manual) {
      this.chunks.push(frame);
      if (this.chunks.length * dur >= MAX_SPEECH_S) this.stopManual();
      return;
    }
    if (!this.handsFree) return;

    // Ngưỡng = nền nhiễu x3 (tự cân theo phòng), nâng lên khi Mira đang nói để không bắt giọng Mira lọt qua loa
    const threshold = Math.max(MIN_THRESHOLD, this.noiseFloor * 3) * (this.isAssistantSpeaking() ? 2.5 : 1);
    if (!this.inSpeech) {
      if (rms >= threshold) {
        this.loudSeconds += dur;
      } else {
        // nền nhiễu chỉ học từ khung yên tĩnh, và học chậm để một tiếng động không làm lệch ngưỡng
        this.noiseFloor = 0.98 * this.noiseFloor + 0.02 * Math.min(rms, threshold);
        this.loudSeconds = Math.max(0, this.loudSeconds - dur);
      }
      if (this.loudSeconds >= START_SPEECH_S) {
        this.inSpeech = true;
        this.silence = 0;
        this.loudSeconds = 0;
        this.chunks = [...this.preRoll];
        this.onSpeechStart();
      }
      return;
    }
    this.chunks.push(frame);
    this.silence = rms < threshold * 0.8 ? this.silence + dur : 0;
    if (this.silence >= END_SILENCE_S || this.chunks.length * dur >= MAX_SPEECH_S) {
      this.inSpeech = false;
      this.finish();
    }
  }

  finish() {
    const frames = this.chunks;
    this.chunks = [];
    const rate = this.ctx.sampleRate;
    const total = frames.reduce((n, f) => n + f.length, 0);
    if (total / rate < MIN_SPEECH_S) return;
    const audio = new Float32Array(total);
    let off = 0;
    for (const f of frames) {
      audio.set(f, off);
      off += f.length;
    }
    // Phòng khi trình duyệt không chịu chạy AudioContext ở 16kHz: tự đổi tần số mẫu
    const n = Math.round((total * RATE) / rate);
    const pcm = new Int16Array(n);
    for (let i = 0; i < n; i++) {
      const s = audio[Math.min(total - 1, Math.round((i * rate) / RATE))];
      pcm[i] = Math.max(-1, Math.min(1, s)) * 32767;
    }
    this.onUtterance(pcm.buffer, n / RATE);
  }
}
