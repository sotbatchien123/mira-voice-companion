"""Mẫu nghe để chọn giọng "kiểu Nhật" (cao, trong, dễ thương) mà vẫn nói tiếng Việt.

Mỗi giọng nữ có sẵn của VieNeu đọc cùng một câu, kèm bản nâng cao giọng +2 nửa cung (giữ nguyên tốc độ).
Ra spikes/audio/out/voices/ (không vào git). Chạy: uv run python spikes/audio/voice_samples.py
"""

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from vieneu import Vieneu

OUT = Path("spikes/audio/out/voices")
TEXT = "Anh về rồi hả? Hôm nay em nhớ anh lắm đó, kể em nghe hôm nay anh làm gì đi!"
FEMALE = ["Mỹ Duyên", "Trúc Ly", "Mai Anh", "Thùy Dung", "Ngọc Huyền", "Ngọc Trân", "Ngọc Linh", "Đoan Trang",
          "Thục Đoan", "Quỳnh Anh", "Kim Thanh"]
SEMITONES = 2

OUT.mkdir(parents=True, exist_ok=True)
tts = Vieneu()
sr = int(getattr(tts, "sample_rate", 48000))
for i, voice in enumerate(FEMALE, 1):
    audio = np.asarray(tts.infer(TEXT, voice=voice), dtype=np.float32)
    name = f"{i:02d}_{voice.replace(' ', '_')}"
    sf.write(OUT / f"{name}.wav", audio, sr)
    sf.write(OUT / f"{name}_cao.wav", librosa.effects.pitch_shift(audio, sr=sr, n_steps=SEMITONES), sr)
    print("xong", name, f"{len(audio) / sr:.1f}s")
