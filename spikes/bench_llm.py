"""So các model Ollama cho vai Mira: VRAM, độ trễ, tag cảm xúc, xưng hô.

uv run python spikes/bench_llm.py qwen3:4b qwen3:8b      (chạy ở thư mục gốc dự án)
"""

import asyncio
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.emotion_tags import EmotionTagParser  # noqa: E402
from app.llm import OllamaLLM  # noqa: E402

URL = "http://127.0.0.1:11434"
PROMPTS = [
    "Chào em, hôm nay em thế nào?", "Anh vừa bị sếp mắng, buồn quá.", "Đoán xem, anh vừa trúng xổ số đó!",
    "Em thích ăn món gì nhất?", "Tối nay mình xem phim gì nhỉ?", "Kể anh nghe một chuyện vui đi.",
    "Em có giận anh không?", "Cuối tuần này em muốn đi đâu chơi?",
]
ROUNDS = 2
BAD_PRONOUN = re.compile(r"(?i)(?<!\w)(tớ|tao|tôi|cậu)(?!\w)|(?<!\w)mình (có thể|thích|đang|nghĩ|muốn|cũng)")
LEAK = re.compile(r"\[[A-Za-z_]{1,16}\]")


def vram_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.strip().splitlines()[0])


def unload_all() -> None:
    for m in httpx.get(f"{URL}/api/ps").json()["models"]:
        httpx.post(f"{URL}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
    time.sleep(3)


async def ask(llm: OllamaLLM, prompt: str) -> dict:
    parser = EmotionTagParser()
    t0 = time.perf_counter()
    first = None
    text, emotions = "", []
    async for kind, value in llm.stream([{"role": "user", "content": prompt}]):
        if kind != "text":
            continue
        chunk = parser.push(value)
        if chunk.text.strip() and first is None:
            first = time.perf_counter() - t0
        text += chunk.text
        emotions += chunk.emotions
    rest = parser.flush()
    return {"first": first, "total": time.perf_counter() - t0, "text": text + rest.text, "emotions": emotions + rest.emotions}


async def bench(model: str) -> None:
    os.environ["OLLAMA_MODEL"] = model
    os.environ.setdefault("OLLAMA_THINK", "false")
    unload_all()
    base = vram_mib()
    llm = OllamaLLM()
    t0 = time.perf_counter()
    await ask(llm, "Xin chào")
    load_s = time.perf_counter() - t0
    loaded = vram_mib()
    ps = {m["name"]: m for m in httpx.get(f"{URL}/api/ps").json()["models"]}

    results = [await ask(llm, p) for _ in range(ROUNDS) for p in PROMPTS]
    firsts = sorted(r["first"] for r in results if r["first"] is not None)
    n = len(results)
    print(f"\n== {model}")
    print(f"  VRAM: nền {base} MiB → đã nạp {loaded} MiB (+{loaded - base}); Ollama báo {ps[model]['size_vram'] / 2**20:.0f} MiB, context {ps[model]['context_length']}")
    print(f"  nạp lần đầu + câu đầu: {load_s:.1f}s")
    print(f"  chữ đầu: trung vị {firsts[len(firsts) // 2]:.2f}s, chậm nhất {firsts[-1]:.2f}s | tổng trung vị {sorted(r['total'] for r in results)[n // 2]:.2f}s")
    print(f"  có tag: {sum(1 for r in results if r['emotions'])}/{n} | lộ tag: {sum(1 for r in results if LEAK.search(r['text']))}"
          f" | xưng hô sai: {sum(1 for r in results if BAD_PRONOUN.search(r['text']))}/{n}")
    for r in results:
        if LEAK.search(r["text"]):
            print(f"    LỘ TAG: {LEAK.findall(r['text'])} trong: {r['text'].strip()[:110]}")
    for r in results[: len(PROMPTS)]:
        print(f"    {r['emotions']} {r['text'].strip()[:110]}")


async def main() -> None:
    for model in sys.argv[1:]:
        await bench(model)


asyncio.run(main())
