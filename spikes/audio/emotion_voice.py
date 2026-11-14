"""Spike spec 008: giọng theo cảm xúc với VieNeu. Tạo mẫu nghe + đo: tín hiệu [cười]/[thở dài] có thành tiếng thật
không (độ dài tăng, STT không đọc ra chữ "cười"), và đổi tốc độ+cao độ (như playbackRate của trình duyệt)."""

import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from dotenv import load_dotenv

load_dotenv(".env")
from vieneu import Vieneu  # noqa: E402

from app.stt import make_stt  # noqa: E402

OUT = Path("spikes/audio/emotion_out")
VOICE = "Mỹ Duyên"
CASES = {
    "happy": "Thật hả anh? Em vui quá đi mất!",
    "sad": "Vậy à anh, em tiếc cho anh quá.",
    "neutral": "Hôm nay anh ăn trưa chưa?",
}
CUES = {"happy": "[cười]", "sad": "[thở dài]"}
RATES = {"happy": 1.05, "sad": 0.94}

tts = Vieneu()
stt = make_stt()
stt.warm_up()
sr = int(getattr(tts, "sample_rate", 48000))


def to16k(a, rate=1.0):
    n = int(len(a) * 16000 / sr / rate)
    x = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


def resample(a, rate):  # giống playbackRate: nhanh hơn thì cao hơn
    n = int(len(a) / rate)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


for emo, text in CASES.items():
    variants = {"plain": text}
    if emo in CUES:
        variants["cue_dau"] = f"{CUES[emo]} {text}"
        first, _, rest = text.partition(" ")
        variants["cue_giua"] = text.replace("? ", f"? {CUES[emo]} ") if "? " in text else text.replace(", ", f", {CUES[emo]} ")
    for name, t in variants.items():
        durs = []
        for k in range(3):
            t0 = time.perf_counter()
            a = tts.infer(t, voice=VOICE)
            took = time.perf_counter() - t0
            durs.append(len(a) / sr)
            if k == 0:
                sf.write(OUT / f"{emo}_{name}.wav", a, sr)
                heard = stt.transcribe(to16k(a))
                if emo in RATES and name == "plain":
                    sf.write(OUT / f"{emo}_plain_toc_do_{RATES[emo]}.wav", resample(a, RATES[emo]), sr)
                if emo in RATES and name == "cue_dau":
                    sf.write(OUT / f"{emo}_cue_dau_toc_do_{RATES[emo]}.wav", resample(a, RATES[emo]), sr)
        print(f"{emo:7s} {name:9s} dài {np.mean(durs):.2f}s (±{np.std(durs):.2f}) tạo {took:.2f}s | STT: {heard}", flush=True)
