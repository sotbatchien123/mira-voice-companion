/**
 * Phát giọng nói theo từng mảnh PCM (event `audio`) nối tiếp nhau, đúng thứ tự,
 * và đo âm lượng đang phát để avatar nhép miệng.
 */
export class AudioPlayer {
  /**
   * @param {{onLevel: (level: number | null) => void, onSegmentStart: (meta: {text: string, emotion: string | null}) => void}} handlers
   *   onLevel nhận âm lượng 0..1 mỗi khung hình khi đang phát, và null khi không còn gì để phát.
   */
  constructor({ onLevel, onSegmentStart }) {
    this.onLevel = onLevel;
    this.onSegmentStart = onSegmentStart;
    this.ctx = null;
    this.analyser = null;
    this.sources = new Set();
    this.timers = new Set();
    this.nextStart = 0;
    this.samples = null;
    this.loop = this.loop.bind(this);
  }

  /** Gọi trong lúc người dùng vừa bấm (gửi tin) để trình duyệt cho phép phát âm thanh. */
  unlock() {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 1024;
      this.analyser.connect(this.ctx.destination);
      this.samples = new Float32Array(this.analyser.fftSize);
    }
    if (this.ctx.state === "suspended") this.ctx.resume();
  }

  get playing() {
    return this.sources.size > 0;
  }

  /** Trình duyệt đã cho phát âm thanh chưa (cần ít nhất một cú bấm của người dùng). */
  get unlocked() {
    return this.ctx?.state === "running";
  }

  /** @param {{part: number, rate: number, pcm: string, text?: string, emotion?: string | null, speed?: number}} chunk */
  enqueue(chunk) {
    this.unlock();
    const bytes = Uint8Array.from(atob(chunk.pcm), (c) => c.charCodeAt(0));
    const pcm = new Int16Array(bytes.buffer, 0, bytes.length >> 1);
    const buffer = this.ctx.createBuffer(1, pcm.length, chunk.rate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) data[i] = pcm[i] / 32768;
    // Mảnh đầu của mỗi đoạn mang chữ + cảm xúc + tốc độ: cả đoạn phát cùng tốc độ (vui nhanh/cao hơn chút, buồn chậm hơn)
    if (chunk.part === 0) this.speed = chunk.speed ?? 1;
    this.schedule(buffer, chunk.part === 0 ? { text: chunk.text, emotion: chunk.emotion ?? null } : null);
  }

  schedule(buffer, meta) {
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.playbackRate.value = this.speed ?? 1;
    src.connect(this.analyser);
    const startAt = Math.max(this.ctx.currentTime + 0.02, this.nextStart);
    this.nextStart = startAt + buffer.duration / src.playbackRate.value;
    src.start(startAt);
    this.sources.add(src);
    src.onended = () => {
      this.sources.delete(src);
      if (!this.playing) this.onLevel(null);
    };
    if (meta) {
      const timer = setTimeout(() => {
        this.timers.delete(timer);
        this.onSegmentStart(meta);
      }, (startAt - this.ctx.currentTime) * 1000);
      this.timers.add(timer);
    }
    if (this.sources.size === 1) requestAnimationFrame(this.loop);
  }

  loop() {
    if (!this.playing) return;
    this.analyser.getFloatTimeDomainData(this.samples);
    let sum = 0;
    for (const s of this.samples) sum += s * s;
    this.onLevel(Math.sqrt(sum / this.samples.length));
    requestAnimationFrame(this.loop);
  }

  /** Dừng ngay mọi mảnh đang phát và đang chờ (khi gửi tin mới hoặc xóa chat). */
  stop() {
    for (const t of this.timers) clearTimeout(t);
    this.timers.clear();
    for (const src of this.sources) {
      src.onended = null;
      src.stop();
    }
    this.sources.clear();
    this.nextStart = 0;
    this.onLevel(null);
  }
}
