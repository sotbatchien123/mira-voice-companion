"""Đo WhisperSTT của app trên giọng VieNeu (3 giọng) + im lặng + tiếng ồn, và in chỉ số từng đoạn để chỉnh bộ lọc.

uv run python spikes/audio/bench_stt.py      (chạy ở thư mục gốc dự án)
"""

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.stt import SAMPLE_RATE, WhisperSTT, keep_segment  # noqa: E402
from spikes.audio.bench_whisper import wer  # noqa: E402

SENTENCES = [
    "Chào em, hôm nay em thế nào?",
    "Anh vừa bị sếp mắng, buồn quá.",
    "Tối nay mình xem phim gì nhỉ?",
    "Em có nhớ anh tên gì không?",
    "Kể anh nghe một chuyện vui đi.",
]
VOICES = ["Mỹ Duyên", "Trúc Ly", "Thái Sơn"]


def to_pcm16(audio: np.ndarray, rate: int) -> bytes:
    n = int(len(audio) * SAMPLE_RATE / rate)
    resampled = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
    return (np.clip(resampled, -1, 1) * 32767).astype("<i2").tobytes()


def main() -> None:
    from vieneu import Vieneu

    tts = Vieneu()
    stt = WhisperSTT()
    t0 = time.perf_counter()
    stt.warm_up()
    print(f"Whisper {stt.model_name} {stt.device}/{stt.compute_type}: nạp + khởi động {time.perf_counter() - t0:.1f}s")

    cases = []
    for voice in VOICES:
        for text in SENTENCES:
            cases.append((f"{voice}", text, to_pcm16(tts.infer(text, voice=voice), getattr(tts, "sample_rate", 48000))))
    rng = np.random.default_rng(0)
    cases.append(("im lặng 2s", "", bytes(2 * SAMPLE_RATE * 2)))
    for amp in (0.01, 0.05):
        noise = rng.normal(0, amp, SAMPLE_RATE * 2)
        cases.append((f"ồn trắng {amp}", "", (np.clip(noise, -1, 1) * 32767).astype("<i2").tobytes()))
    hum = 0.05 * np.sin(2 * np.pi * 50 * np.arange(SAMPLE_RATE * 2) / SAMPLE_RATE)
    cases.append(("ù 50Hz", "", (hum * 32767).astype("<i2").tobytes()))

    model = stt._load()
    lat, wers = [], []
    for label, ref, pcm in cases:
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        t0 = time.perf_counter()
        text = stt.transcribe(pcm)
        took = time.perf_counter() - t0
        # chỉ số thô (không VAD lọc) để xem bộ lọc có cần thiết không
        raw = list(model.transcribe(audio, language="vi", beam_size=1, vad_filter=False, condition_on_previous_text=False)[0])
        stats = " ".join(f"[nsp {s.no_speech_prob:.2f} lp {s.avg_logprob:.2f} cr {s.compression_ratio:.1f} "
                         f"{'giữ' if keep_segment(s.no_speech_prob, s.avg_logprob, s.compression_ratio, s.text) else 'BỎ'} '{s.text.strip()[:25]}']"
                         for s in raw)
        line = f"{label:12s} {len(audio) / SAMPLE_RATE:4.1f}s → {took:.2f}s | "
        if ref:
            w = wer(ref, text)
            lat.append(took)
            wers.append(w)
            line += f"WER {w:4.0%} | {text}"
        else:
            line += f"kết quả: {text!r}"
        print(line)
        print("    thô (không VAD):", stats or "(không có đoạn)")
    print(f"\nTổng kết: thời gian nhận dạng trung vị {np.median(lat):.2f}s, chậm nhất {max(lat):.2f}s | "
          f"WER trung bình {np.mean(wers):.0%}, câu sai >15%: {sum(w > 0.15 for w in wers)}/{len(wers)}")


if __name__ == "__main__":
    main()
