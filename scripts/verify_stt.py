"""Kiểm chứng /api/stt với server THẬT: câu nói do VieNeu đọc (giả làm người dùng), im lặng và tiếng ồn.

uv run python scripts/verify_stt.py [--url http://127.0.0.1:8000] [--wav-out đường_dẫn.wav]

Ứng với SC-001..003 của specs/003-voice-input-stt. Giọng tổng hợp sạch hơn giọng thật qua mic laptop,
nên con số ở đây là cận trên; người dùng vẫn cần thử bằng mic thật.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import wave

import httpx
import numpy as np

RATE = 16000
SENTENCES = [
    "Chào em, hôm nay em thế nào?",
    "Anh vừa bị sếp mắng, buồn quá.",
    "Tối nay mình xem phim gì nhỉ?",
    "Em có nhớ anh tên gì không?",
    "Kể anh nghe một chuyện vui đi.",
]
VOICE = "Ngọc Huyền"  # giọng khác Mira để giả làm người dùng


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


def to_16k(audio: np.ndarray, rate: int) -> np.ndarray:
    n = int(len(audio) * RATE / rate)
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)


def pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--wav-out", help="lưu câu đầu (kèm khoảng lặng) thành WAV để thử mic giả lập trên trình duyệt")
    args = ap.parse_args()

    from vieneu import Vieneu

    tts = Vieneu()
    rate = int(getattr(tts, "sample_rate", 48000))
    client = httpx.Client(timeout=60)
    print("health stt:", client.get(f"{args.url}/api/health").json().get("stt"))

    latencies, wers = [], []
    for i, text in enumerate(SENTENCES):
        audio = to_16k(tts.infer(text, voice=VOICE), rate)
        if i == 0 and args.wav_out:
            padded = np.concatenate([np.zeros(RATE // 2, np.float32), audio, np.zeros(int(RATE * 1.5), np.float32)])
            with wave.open(args.wav_out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(pcm16(padded))
        t0 = time.perf_counter()
        res = client.post(f"{args.url}/api/stt", content=pcm16(audio), headers={"Content-Type": "application/octet-stream"})
        took = time.perf_counter() - t0
        body = res.json()
        w = wer(text, body.get("text", ""))
        latencies.append(took)
        wers.append(w)
        print(f"  {len(audio) / RATE:.1f}s audio → {took:.2f}s (server {body.get('ms')}ms) | WER {w:4.0%} | {body.get('text')!r}")

    rng = np.random.default_rng(1)
    noises = {
        "im lặng 2s": np.zeros(RATE * 2, np.float32),
        "ồn trắng": rng.normal(0, 0.05, RATE * 2).astype(np.float32),
        "ù 50Hz": (0.05 * np.sin(2 * np.pi * 50 * np.arange(RATE * 2) / RATE)).astype(np.float32),
    }
    fake = 0
    for label, audio in noises.items():
        body = client.post(f"{args.url}/api/stt", content=pcm16(audio), headers={"Content-Type": "application/octet-stream"}).json()
        fake += bool(body.get("text"))
        print(f"  {label}: {body.get('text')!r}")

    ok_latency = sum(t <= 2.0 for t in latencies)
    ok_wer = sum(w <= 0.15 for w in wers)
    print("\n=== Tổng kết ===")
    print(f"SC-001 chữ có trong ≤ 2s: {ok_latency}/{len(latencies)} (cần ≥ 4)")
    print(f"SC-002 sai ≤ 15% từ: {ok_wer}/{len(wers)} | WER trung bình {np.mean(wers):.0%}")
    print(f"SC-003 câu bịa từ im lặng/tiếng ồn: {fake} (cần 0)")
    return 0 if ok_latency >= 4 and fake == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
