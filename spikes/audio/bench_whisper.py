"""Đo faster-whisper trên các WAV do bench_piper.py tạo: độ trễ và tỉ lệ sai từ (WER).

uv run --no-project --python 3.12 --with faster-whisper python bench_whisper.py cpu
uv run --no-project --python 3.12 --with faster-whisper --with nvidia-cublas-cu12 --with nvidia-cudnn-cu12 python bench_whisper.py cuda

Lưu ý: audio là giọng tổng hợp, sạch, nên WER ở đây lạc quan hơn giọng người thật qua mic laptop.
"""

import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
SENTENCES = [
    "Chào anh! Em ổn mà, đang nghe nhạc và xem anime đây. Anh làm gì vậy?",
    "Anh buồn thật à? Em biết anh đang buồn, không sao đâu, cứ kể cho em nghe đi.",
    "Ô! Anh trúng xổ số à? Vậy anh sẽ làm gì trước tiên?",
]


def words(s: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", s.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)] / len(r)


def load_16k(path: Path):
    # Tự đọc WAV thay vì để faster-whisper dùng PyAV (bản av mới không tương thích)
    import wave

    import numpy as np

    with wave.open(str(path)) as w:
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = int(len(pcm) * 16000 / rate)
    return np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)


def add_cuda_dll_dirs() -> None:
    # Trên Windows, DLL cuBLAS/cuDNN từ pip nằm trong site-packages/nvidia/*/bin
    import os

    # uv --with đặt gói ở thư mục riêng, nên dò theo sys.path thay vì site.getsitepackages()
    for sp in sys.path:
        for bin_dir in Path(sp).glob("nvidia/*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


def main() -> None:
    device = sys.argv[1] if len(sys.argv) > 1 else "cpu"
    if device == "cuda":
        add_cuda_dll_dirs()
    from faster_whisper import WhisperModel

    compute = "int8" if device == "cpu" else "float16"
    t0 = time.perf_counter()
    model = WhisperModel("small", device=device, compute_type=compute)
    print(f"== whisper small | {device} {compute} | nạp model {time.perf_counter() - t0:.1f}s")

    wavs = [load_16k(HERE / "out" / f"piper_vi_VN-vais1000-medium_{i + 1}.wav") for i in range(len(SENTENCES))]
    list(model.transcribe(wavs[0], language="vi")[0])  # khởi động, không tính

    for ref, wav in zip(SENTENCES, wavs):
        t0 = time.perf_counter()
        segments, info = model.transcribe(wav, language="vi", beam_size=1, vad_filter=False)
        text = " ".join(s.text.strip() for s in segments)
        took = time.perf_counter() - t0
        print(f"  {info.duration:.1f}s audio → {took:.2f}s | WER {wer(ref, text):.0%} | {text}")


if __name__ == "__main__":
    main()
