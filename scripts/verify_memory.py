"""Kiểm chứng trí nhớ dài hạn với server + model THẬT (specs/004-long-term-memory, SC-001..004).

uv run python scripts/verify_memory.py [--url http://127.0.0.1:8000]

Chỉ chạy khi trí nhớ đang trống (để không đụng điều nhớ thật của người dùng) và tự xóa sạch khi xong.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ask(client: httpx.Client, url: str, history: list[dict]) -> tuple[str, float]:
    t0 = time.perf_counter()
    first = None
    raw = ""
    with client.stream("POST", f"{url}/api/chat", json={"messages": history}) as res:
        for line in res.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev["type"] == "text" and first is None and ev["text"].strip():
                first = time.perf_counter() - t0
            if ev["type"] in ("done", "error"):
                raw = ev.get("raw") or ev.get("message", "")
    return raw, first or 0.0


def facts(client: httpx.Client, url: str) -> list[dict]:
    return client.get(f"{url}/api/memory").json()["facts"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    url = ap.parse_args().url
    client = httpx.Client(timeout=180)
    if facts(client, url):
        print("Trí nhớ đang có dữ liệu thật của người dùng -> không chạy để khỏi làm mất. Xóa trong bảng 'Trí nhớ' trước nếu muốn thử.")
        return 2

    ok = True
    try:
        # Phiên 1: kể chuyện
        history: list[dict] = []
        first_texts = []
        for msg in ["Chào em!", "Anh tên là Khoa, anh làm lập trình viên ở Đà Nẵng.", "Anh nuôi một con mèo tên Mướp, lười lắm."]:
            history.append({"role": "user", "content": msg})
            raw, first = ask(client, url, history)
            first_texts.append(first)
            history.append({"role": "assistant", "content": raw})
        print("Sau phiên 1, Mira nhớ:", [f["text"] for f in facts(client, url)])

        # Phiên 2: như vừa bấm Xóa chat -> không có lịch sử
        raw, first = ask(client, url, [{"role": "user", "content": "Em còn nhớ anh tên gì, làm nghề gì, nuôi con gì không?"}])
        first_texts.append(first)
        hits = [k for k in ("Khoa", "lập trình", "Mướp") if k.lower() in raw.lower()]
        print(f"\nPhiên mới, Mira trả lời: {raw}\n  -> nhớ đúng {len(hits)}/3 {hits}")
        ok &= len(hits) == 3

        # Chuyển nhà: chỉ còn một điều về nơi ở
        ask(client, url, [{"role": "user", "content": "À anh chuyển vào Sài Gòn sống rồi nhé."}])
        places = [f["text"] for f in facts(client, url) if f["kind"] == "noi_o"]
        print(f"\nSau khi chuyển nhà, điều về nơi ở: {places}")
        ok &= len(places) == 1 and "Sài Gòn" in places[0]

        # Chào hỏi / câu hỏi thuần: không sinh điều nhớ
        before = len(facts(client, url))
        for msg in ["Hôm nay em thế nào?", "Em thích ăn món gì nhất?", "Kể anh nghe chuyện vui đi.", "Ngủ ngon nha em."]:
            ask(client, url, [{"role": "user", "content": msg}])
        extra = len(facts(client, url)) - before
        print(f"4 câu chào hỏi/câu hỏi -> thêm {extra} điều (cần 0)")
        ok &= extra == 0

        print(f"\nChữ đầu (có trí nhớ trong prompt): {[round(t, 2) for t in first_texts]}s")
        print("Mira nhớ cuối cùng:", [f"[{f['kind']}] {f['text']}" for f in facts(client, url)])

        # Token thật khi lịch sử dài: dựng đúng prompt như server rồi hỏi Ollama đếm
        from app.main import ChatTurn, trim_history
        from app.memory import Fact, system_prompt

        long_turns = [ChatTurn(role=r, content="Hôm nay anh đi làm về muộn, trời mưa to, kẹt xe cả tiếng đồng hồ. " * 4)
                      for r in ["user", "assistant"] * 20] + [ChatTurn(role="user", content="Em nghĩ sao?")]
        kept = trim_history(long_turns)
        known = [Fact(**{k: f[k] for k in ("id", "kind", "text", "said_on")}) for f in facts(client, url)]
        system = system_prompt(datetime.now(), known)
        res = httpx.post("http://127.0.0.1:11434/api/chat", timeout=120, json={
            "model": "qwen3:8b", "stream": False, "think": False, "options": {"num_predict": 1},
            "messages": [{"role": "system", "content": system}, *kept]}).json()
        used = res.get("prompt_eval_count")
        print(f"\nLịch sử 41 lượt dài -> giữ {len(kept)} lượt; prompt thật = {used} token (cần ≤ 4096 - 512 = 3584)")
        ok &= used is not None and used <= 3584
    finally:
        client.delete(f"{url}/api/memory")  # dọn điều nhớ thử nghiệm
        print("\nĐã xóa trí nhớ thử nghiệm:", facts(client, url) == [])
    print("\n=== KẾT QUẢ:", "ĐẠT" if ok else "CHƯA ĐẠT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
