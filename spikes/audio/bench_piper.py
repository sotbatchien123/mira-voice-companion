"""Đo Piper TTS tiếng Việt trên CPU: thời gian ra audio đầu tiên, RTF, và lưu WAV để nghe.

uv run --no-project --python 3.12 --with piper-tts python bench_piper.py
"""

import time
import wave
from pathlib import Path

from piper import PiperVoice

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# Câu trả lời thật của Mira lấy từ các lần chạy qwen3:8b
SENTENCES = [
    "Chào anh! Em ổn mà, đang nghe nhạc và xem anime đây. Anh làm gì vậy?",
    "Anh buồn thật à? Em biết anh đang buồn, không sao đâu, cứ kể cho em nghe đi.",
    "Ô! Anh trúng xổ số à? Vậy anh sẽ làm gì trước tiên?",
]

for name in ("vi_VN-vais1000-medium", "vi_VN-25hours_single-low"):
    t0 = time.perf_counter()
    voice = PiperVoice.load(HERE / "models" / "piper" / f"{name}.onnx")
    print(f"\n== {name}: nạp model {time.perf_counter() - t0:.2f}s")
    voice.synthesize("Xin chào.")  # khởi động onnxruntime, không tính
    list(voice.synthesize("Xin chào."))

    for i, text in enumerate(SENTENCES):
        t0 = time.perf_counter()
        first = None
        pcm = bytearray()
        rate = None
        for chunk in voice.synthesize(text):
            if first is None:
                first = time.perf_counter() - t0
            pcm += chunk.audio_int16_bytes
            rate = chunk.sample_rate
        total = time.perf_counter() - t0
        dur = len(pcm) / 2 / rate
        print(f"  câu {i + 1}: audio đầu {first:.2f}s | tạo xong {total:.2f}s | dài {dur:.1f}s | RTF {total / dur:.3f}")
        with wave.open(str(OUT / f"piper_{name}_{i + 1}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(pcm))
