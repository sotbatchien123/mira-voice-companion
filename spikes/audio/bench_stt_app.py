"""Đo engine STT của app (đúng như server dùng, có VAD chặn) trên FLEURS người thật + im lặng/tiếng ồn.

uv run --with pyarrow python spikes/audio/bench_stt_app.py [zipformer|whisper] [số_câu]
"""

import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ["STT_PROVIDER"] = sys.argv[1] if len(sys.argv) > 1 else "zipformer"
from app.stt import SAMPLE_RATE, make_stt  # noqa: E402
from spikes.audio.bench_asr_compare import load_samples, wer  # noqa: E402


def pcm(a: np.ndarray) -> bytes:
    return (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()


def main() -> None:
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    stt = make_stt()
    stt.warm_up()
    samples = load_samples(n)
    errs = words = 0
    lat = []
    for audio, ref in samples:
        t0 = time.perf_counter()
        hyp = stt.transcribe(pcm(audio))
        lat.append(time.perf_counter() - t0)
        e, w = wer(ref, hyp)
        errs, words = errs + e, words + w
    lat.sort()
    print(f"{stt.name} (app, có VAD): {len(samples)} câu FLEURS | WER {errs / words:.1%} | trễ trung vị {lat[len(lat) // 2]:.2f}s, "
          f"p95 {lat[int(len(lat) * 0.95)]:.2f}s")
    rng = np.random.default_rng(1)
    noise = {
        "im lặng": np.zeros(SAMPLE_RATE * 2),
        "ồn trắng 0.05": rng.normal(0, 0.05, SAMPLE_RATE * 2),
        "ồn trắng 0.15": rng.normal(0, 0.15, SAMPLE_RATE * 2),
        "ù 50Hz": 0.05 * np.sin(2 * np.pi * 50 * np.arange(SAMPLE_RATE * 2) / SAMPLE_RATE),
        "gõ phím (xung)": np.where(rng.random(SAMPLE_RATE * 2) > 0.998, 0.6, 0.0) * rng.normal(1, 0.2, SAMPLE_RATE * 2),
    }
    for label, audio in noise.items():
        print(f"  {label}: {stt.transcribe(pcm(audio))!r}")


if __name__ == "__main__":
    main()
