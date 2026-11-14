"""So Zipformer-30M (VoiceDeck, sherpa-onnx) với Whisper small (app hiện tại) trên giọng NGƯỜI THẬT (FLEURS vi_vn test).

uv run --with sherpa-onnx --with pyarrow python spikes/audio/bench_asr_compare.py [số_câu]

Lưu ý: FLEURS có trong danh sách dữ liệu huấn luyện của Zipformer (có thể phần train), nên WER của nó có thể lạc quan.
"""

import io
import random
import re
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pyarrow.parquet as pq
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.stt import WhisperSTT  # noqa: E402

PARQUET_URL = "https://huggingface.co/api/datasets/google/fleurs/parquet/vi_vn/test/0.parquet"
CACHE = ROOT / "spikes" / "audio" / "models" / "fleurs_vi_test.parquet"
ZIP_DIR = Path(r"D:\voice_models\Zipformer-30M-RNNT-6000h")
RATE = 16000


def norm(s: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", s.lower()).split()


def wer(ref: str, hyp: str) -> tuple[int, int]:
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)], len(r)


def load_samples(n: int):
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        print("tải FLEURS vi_vn test...")
        with httpx.stream("GET", PARQUET_URL, follow_redirects=True, timeout=600) as res:
            res.raise_for_status()
            with CACHE.open("wb") as f:
                for chunk in res.iter_bytes():
                    f.write(chunk)
    table = pq.read_table(CACHE, columns=["audio", "transcription", "raw_transcription"]).to_pylist()
    random.Random(42).shuffle(table)
    out = []
    for row in table[:n]:
        audio, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(1)
        if rate != RATE:
            k = int(len(audio) * RATE / rate)
            audio = np.interp(np.linspace(0, len(audio) - 1, k), np.arange(len(audio)), audio).astype(np.float32)
        out.append((audio, row["raw_transcription"] or row["transcription"]))
    return out


def zipformer():
    import sherpa_onnx

    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(ZIP_DIR / "encoder-epoch-20-avg-10.int8.onnx"),
        decoder=str(ZIP_DIR / "decoder-epoch-20-avg-10.int8.onnx"),
        joiner=str(ZIP_DIR / "joiner-epoch-20-avg-10.int8.onnx"),
        tokens=str(ZIP_DIR / "config.json"),
        modeling_unit="bpe",
        bpe_vocab=str(ZIP_DIR / "bpe.model"),
        num_threads=8,
        sample_rate=RATE,
        provider="cpu",
    )

    def run(audio: np.ndarray) -> str:
        stream = rec.create_stream()
        stream.accept_waveform(RATE, audio)
        rec.decode_stream(stream)
        return stream.result.text.strip()

    return run


def whisper():
    stt = WhisperSTT()
    stt.warm_up()
    return lambda audio: stt.transcribe((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    samples = load_samples(n)
    total_audio = sum(len(a) for a, _ in samples) / RATE
    print(f"{len(samples)} câu người thật, tổng {total_audio:.0f}s, trung bình {total_audio / len(samples):.1f}s/câu")
    for name, make in (("zipformer-30M", zipformer), ("whisper-small", whisper)):
        t0 = time.perf_counter()
        run = make()
        load = time.perf_counter() - t0
        run(samples[0][0])  # khởi động
        errs = words = 0
        lat = []
        examples = []
        for audio, ref in samples:
            t0 = time.perf_counter()
            hyp = run(audio)
            lat.append(time.perf_counter() - t0)
            e, w = wer(ref, hyp)
            errs, words = errs + e, words + w
            if len(examples) < 3:
                examples.append((ref, hyp))
        lat.sort()
        print(f"\n== {name}: nạp {load:.1f}s | WER {errs / words:.1%} | trễ trung vị {lat[len(lat) // 2]:.2f}s, "
              f"p95 {lat[int(len(lat) * 0.95)]:.2f}s | RTF {sum(lat) / total_audio:.3f}")
        for ref, hyp in examples:
            print(f"   gốc: {ref}\n   ra : {hyp}")


if __name__ == "__main__":
    main()
