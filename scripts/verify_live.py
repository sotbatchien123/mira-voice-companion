"""Kiểm chứng với model THẬT (không phải test tự động): đo độ trễ, tỷ lệ có tag cảm xúc, lộ tag.

Cách dùng (server phải đang chạy):
    uv run python scripts/verify_live.py [--url http://127.0.0.1:8000] [--warmup] [--voice]

Ứng với SC-001..003 của specs/001-local-chat-mvp; thêm --voice để đo SC-001, SC-003 của specs/002-voice-tts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

import httpx

PROMPTS = [
    "Chào em, hôm nay em thế nào?",
    "Anh vừa bị sếp mắng, buồn quá.",
    "Đoán xem, anh vừa trúng xổ số đó!",
    "Em thích ăn món gì nhất?",
    "Tối nay mình xem phim gì nhỉ?",
]
TAG_LEAK = re.compile(r"\[[A-Za-z_]{1,16}\]")
# Ký tự không nên bị đọc: emoji và các ký hiệu ngoài chữ/số/dấu câu cơ bản
UNSPEAKABLE = re.compile(r"[^\w\s.,!?;:…'\"\-()%/]")


def ask(client: httpx.Client, url: str, text: str, voice: bool = False) -> dict:
    start = time.perf_counter()
    first_text_at = None
    first_audio_at = None
    emotions: list[str] = []
    spoken: list[str] = []
    voice_errors: list[str] = []
    shown = ""
    end = None
    body = {"messages": [{"role": "user", "content": text}], "voice": voice}
    with client.stream("POST", f"{url}/api/chat", json=body) as res:
        res.raise_for_status()
        for line in res.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev["type"] == "text":
                if first_text_at is None:
                    first_text_at = time.perf_counter() - start
                shown += ev["text"]
            elif ev["type"] == "emotion":
                emotions.append(ev["emotion"])
            elif ev["type"] == "audio":
                if first_audio_at is None:
                    first_audio_at = time.perf_counter() - start
                if ev.get("part", 0) == 0:  # chữ của đoạn chỉ đi kèm mảnh đầu
                    spoken.append(ev["text"])
            elif ev["type"] == "tts_error":
                voice_errors.append(ev["message"])
            else:
                end = ev
    return {
        "prompt": text,
        "first_text_s": first_text_at,
        "total_s": time.perf_counter() - start,
        "emotions": emotions,
        "shown": shown.strip(),
        "leak": bool(TAG_LEAK.search(shown)),
        "end": end,
        "first_audio_s": first_audio_at,
        "spoken": spoken,
        "bad_speech": [t for t in spoken if TAG_LEAK.search(t) or UNSPEAKABLE.search(t)],
        "voice_errors": voice_errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--warmup", action="store_true", help="gửi 1 câu trước để nạp model vào GPU")
    ap.add_argument("--voice", action="store_true", help="bật giọng nói, đo thời gian tới audio đầu tiên")
    args = ap.parse_args()

    with httpx.Client(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
        print("health:", client.get(f"{args.url}/api/health").json())
        if args.warmup:
            w = ask(client, args.url, "Xin chào", args.voice)
            print(f"warmup: tổng {w['total_s']:.1f}s, kết thúc {w['end']}")

        results = [ask(client, args.url, p, args.voice) for p in PROMPTS]

    for r in results:
        ft = f"{r['first_text_s']:.2f}s" if r["first_text_s"] is not None else "—"
        print(f"\n> {r['prompt']}\n  chữ đầu: {ft} | tổng: {r['total_s']:.1f}s | cảm xúc: {r['emotions']}"
              f" | lộ tag: {r['leak']} | kết thúc: {r['end'] and r['end']['type']}")
        print(f"  {r['shown']}")
        if args.voice:
            fa = f"{r['first_audio_s']:.2f}s" if r["first_audio_s"] is not None else "—"
            print(f"  audio đầu: {fa} | {len(r['spoken'])} đoạn | đọc: {r['spoken']}")

    ok_latency = sum(1 for r in results if r["first_text_s"] is not None and r["first_text_s"] <= 2.0)
    ok_emotion = sum(1 for r in results if r["emotions"])
    leaks = sum(1 for r in results if r["leak"])
    errors = sum(1 for r in results if not r["end"] or r["end"]["type"] != "done")
    print("\n=== Tổng kết ===")
    print(f"SC-001 chữ đầu ≤ 2s: {ok_latency}/{len(results)} (cần ≥ 4)")
    print(f"SC-002 có tag cảm xúc: {ok_emotion}/{len(results)} (cần ≥ 4; tiếng Việt: xem bằng mắt ở trên)")
    print(f"SC-003 lộ tag: {leaks} (cần 0)")
    print(f"Lỗi: {errors}")
    ok = ok_latency >= 4 and ok_emotion >= 4 and leaks == 0 and errors == 0
    if args.voice:
        ok_audio = sum(1 for r in results if r["first_audio_s"] is not None and r["first_audio_s"] <= 1.0)
        bad = [t for r in results for t in r["bad_speech"]]
        verrs = [m for r in results for m in r["voice_errors"]]
        print(f"[002] SC-001 audio đầu ≤ 1s: {ok_audio}/{len(results)} (cần ≥ 4)")
        print(f"[002] SC-003 đoạn đọc có emoji/tag: {len(bad)} (cần 0) {bad}")
        print(f"[002] lỗi giọng: {verrs}")
        ok = ok and ok_audio >= 4 and not bad and not verrs
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
