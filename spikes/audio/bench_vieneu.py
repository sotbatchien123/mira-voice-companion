"""Đo VieNeu-TTS v3 Turbo trên CPU (ONNX, không torch) và tạo mẫu các giọng để nghe chọn.

uv run --no-project --python 3.12 --with vieneu python bench_vieneu.py [fp32|int8]
"""

import inspect
import subprocess
import sys
import time
from pathlib import Path

from vieneu import Vieneu

HERE = Path(__file__).parent
OUT = HERE / "out" / "vieneu"
OUT.mkdir(parents=True, exist_ok=True)
PRECISION = sys.argv[1] if len(sys.argv) > 1 else "fp32"

SENTENCES = [
    "Chào anh! Em ổn mà, đang nghe nhạc và xem anime đây. Anh làm gì vậy?",
    "Anh buồn thật à? Em biết anh đang buồn, không sao đâu, cứ kể cho em nghe đi.",
]


def vram() -> str:
    return subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout.strip()


print("VRAM trước:", vram())
t0 = time.perf_counter()
tts = Vieneu(precision=PRECISION) if PRECISION != "fp32" else Vieneu()
print(f"== {type(tts).__name__} ({PRECISION}) nạp {time.perf_counter() - t0:.1f}s | VRAM sau: {vram()}")
for name in ("infer", "infer_stream", "list_preset_voices", "save"):
    fn = getattr(tts, name, None)
    print(f"  {name}{inspect.signature(fn) if fn else ' — không có'}")

voices = list(tts.list_preset_voices())
print("giọng có sẵn:", voices)

tts.infer("Xin chào.")  # khởi động, không tính
sr = getattr(tts, "sample_rate", 48000)

# Độ trễ stream và RTF với giọng mặc định
for text in SENTENCES:
    t0 = time.perf_counter()
    first = None
    n = 0
    for chunk in tts.infer_stream(text):
        if first is None:
            first = time.perf_counter() - t0
        n += len(chunk)
    total = time.perf_counter() - t0
    print(f"  stream: audio đầu {first:.2f}s | xong {total:.2f}s | dài {n / sr:.1f}s | RTF {total / (n / sr):.2f}")

# Mẫu cho từng giọng (để người dùng nghe chọn)
for label, voice_id in voices:
    t0 = time.perf_counter()
    audio = tts.infer(SENTENCES[0], voice=voice_id)
    tts.save(audio, str(OUT / f"{voice_id}.wav"))
    print(f"  mẫu {label} ({voice_id}): {time.perf_counter() - t0:.2f}s")
