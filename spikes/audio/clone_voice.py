"""Thử nhân bản giọng: VieNeu đọc tiếng Việt bằng âm sắc của một đoạn mẫu (vd giọng Amitaro, tự tải về máy).

Đoạn mẫu cắt còn 8 giây. Ra spikes/audio/out/clone/ (không vào git), kèm thời gian tạo và chữ STT nghe lại.
Chạy: uv run python spikes/audio/clone_voice.py <file_mẫu.wav> [...]
"""

import sys
import time
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from dotenv import load_dotenv

load_dotenv(".env")
from vieneu import Vieneu  # noqa: E402

from app.stt import make_stt  # noqa: E402

OUT = Path("spikes/audio/out/clone")
TEXT = "Anh về rồi hả? Hôm nay em nhớ anh lắm đó, kể em nghe hôm nay anh làm gì đi!"
REF_SECONDS = 8.0

OUT.mkdir(parents=True, exist_ok=True)
tts = Vieneu()
sr = int(getattr(tts, "sample_rate", 48000))
stt = make_stt()
for src in map(Path, sys.argv[1:]):
    audio, rate = sf.read(src, dtype="float32")
    ref = OUT / f"ref_{src.stem}.wav"
    sf.write(ref, audio[: int(rate * REF_SECONDS)], rate)
    started = time.perf_counter()
    out = np.asarray(tts.infer(TEXT, ref_audio=str(ref)), dtype=np.float32)
    took = time.perf_counter() - started
    sf.write(OUT / f"{src.stem}.wav", out, sr)
    pcm = (np.clip(librosa.resample(out, orig_sr=sr, target_sr=16000), -1, 1) * 32767).astype("<i2").tobytes()
    print(f"{src.stem}: {len(out) / sr:.1f}s audio, tạo mất {took:.1f}s | STT: {stt.transcribe(pcm)}")
