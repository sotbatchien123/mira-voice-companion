"""Đo giọng tiếng Nhật (spec 011) với server và model thật: tỉ lệ câu có <ja>, chữ đầu / giọng đầu, chữ Nhật lọt màn hình.

Server phải đang chạy với giọng cần đo (vd TTS_PROVIDER=voicevox, MEMORY_ENABLED=false để không ghi trí nhớ).
Chạy: uv run python scripts/verify_ja_voice.py [--url http://127.0.0.1:8002] [--n 20]
"""

import argparse
import json
import re
import statistics
import time

import httpx

MESSAGES = [
    "Chào em, hôm nay em thế nào?", "Anh vừa đi làm về, mệt quá.", "Kể anh nghe một chuyện vui đi.",
    "Em thích ăn gì nhất?", "Cuối tuần này anh định đi Đà Lạt.", "Hôm nay trời mưa to ghê.",
    "Anh bị sếp mắng vì nộp báo cáo trễ.", "Em có biết hát không?", "Mèo nhà anh vừa đẻ ba con.",
    "Anh đang học tiếng Nhật đó.", "Tối nay ăn phở hay bún chả nhỉ?", "Em có buồn khi anh đi vắng không?",
    "Anh mới mua một cái bàn phím cơ.", "Sao em dễ thương vậy?", "Mai anh có buổi phỏng vấn quan trọng.",
    "Anh xem phim kinh dị xong sợ quá.", "Em nghĩ anh nên ngủ sớm không?", "Hôm nay anh được tăng lương!",
    "Bạn anh vừa chuyển ra nước ngoài.", "Chúc em ngủ ngon nha.",
]
JA = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
SENTENCE = re.compile(r"[.!?…]+")
JA_BLOCK = re.compile(r"<(?:ja|jp)>[\s\S]*?(?:</(?:ja|jp)>|$)", re.IGNORECASE)


def silent_sentences(raw: str) -> int:
    """Số câu Việt không có <ja> nào theo sau (sẽ im); một <ja> gom nhiều câu ngắn vẫn tính là có giọng."""
    parts = JA_BLOCK.split(raw)
    n = 0
    for i, part in enumerate(parts):
        k = len(SENTENCE.findall(part))
        n += max(0, k - 1) if i < len(parts) - 1 else k
    return n


assert silent_sentences("A! <ja>あ</ja> B. <ja>い</ja>") == 0
assert silent_sentences("A! B. <ja>あい</ja> C.") == 2


def run_one(client: httpx.Client, url: str, text: str) -> dict:
    start = time.perf_counter()
    first_text = first_audio = None
    shown, raw, segments = [], "", 0
    body = {"messages": [{"role": "user", "content": text}], "voice": True}
    with client.stream("POST", f"{url}/api/chat", json=body, timeout=180) as res:
        for line in res.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            now = round((time.perf_counter() - start) * 1000)
            if ev["type"] == "text":
                first_text = first_text or now
                shown.append(ev["text"])
            elif ev["type"] == "audio" and ev["part"] == 0:
                first_audio = first_audio or now
                segments += 1
            elif ev["type"] in ("done", "error"):
                raw = ev.get("raw", "")
                if ev["type"] == "error":
                    print("  lỗi:", ev["message"])
    display = "".join(shown)
    return {"first_text": first_text, "first_audio": first_audio, "segments": segments,
            "sentences": len(SENTENCE.findall(display)) or 1, "ja_tags": raw.lower().count("<ja>"), "silent": silent_sentences(raw),
            "leak": bool(JA.search(display) or "<ja" in display.lower()), "display": display, "raw": raw}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8002")
    ap.add_argument("--n", type=int, default=len(MESSAGES))
    args = ap.parse_args()
    rows = []
    with httpx.Client() as client:
        for text in MESSAGES[: args.n]:
            r = run_one(client, args.url, text)
            rows.append(r)
            print(f"{r['first_text']}ms chữ / {r['first_audio']}ms giọng | {r['ja_tags']} <ja> / {r['sentences']} câu, {r['silent']} câu im"
                  f"{' | LỌT CHỮ NHẬT' if r['leak'] else ''} | {r['raw'][:120]!r}")
    full = sum(r["silent"] == 0 for r in rows)
    audio = [r["first_audio"] for r in rows if r["first_audio"]]
    print(f"\nKhông câu nào im: {full}/{len(rows)}; tổng câu im {sum(r['silent'] for r in rows)}/"
          f"{sum(r['sentences'] for r in rows)}; có giọng: {len(audio)}/{len(rows)}; lọt chữ Nhật: "
          f"{sum(r['leak'] for r in rows)}")
    print(f"Trung vị chữ đầu {statistics.median(r['first_text'] or 0 for r in rows)}ms, giọng đầu "
          f"{statistics.median(audio) if audio else '-'}ms")


if __name__ == "__main__":
    main()
