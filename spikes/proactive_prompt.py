"""Spike: Mira tự chào khi mở app / hỏi thăm khi im lâu. Thử prompt với qwen3:8b trên vài tình huống.

uv run python spikes/proactive_prompt.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.emotion_tags import parse_complete  # noqa: E402
from app.memory import Fact, system_prompt  # noqa: E402

FACTS = [
    Fact("1", "ten", "Anh tên là Khoa", "2026-11-10"),
    Fact("2", "thu_cung", "Anh nuôi một con mèo tên Mướp", "2026-11-10"),
    Fact("3", "su_kien", "Anh đi phỏng vấn ở FPT vào thứ Bảy tuần sau", "2026-11-07"),
]

CASES = [
    ("mở app buổi sáng, vắng 1 ngày, có trí nhớ", datetime(2026, 11, 14, 7, 40), "greet", "khoảng 1 ngày", FACTS),
    ("mở app buổi tối, vắng 3 tiếng, có trí nhớ", datetime(2026, 11, 14, 21, 30), "greet", "khoảng 3 tiếng", FACTS),
    ("lần đầu gặp, chưa biết gì", datetime(2026, 11, 14, 15, 0), "greet", "chưa từng nói chuyện", []),
    ("đang mở app nhưng im 10 phút", datetime(2026, 11, 14, 22, 10), "checkin", "10 phút", FACTS),
]


def instruction(kind: str, gap: str) -> str:
    if kind == "greet":
        situation = f"Anh vừa mở ứng dụng. Lần trò chuyện trước: {gap}."
        task = ("Hãy chủ động chào anh một câu ngắn (1-2 câu), hợp với giờ hiện tại. Nếu trong những điều đã biết có chuyện "
                "đáng hỏi thăm (sự kiện vừa qua hoặc sắp tới, thú cưng...) thì hỏi thăm MỘT chuyện thôi; không có thì chào bình thường.")
    else:
        situation = f"Anh đang mở ứng dụng nhưng im lặng đã {gap}."
        task = ("Hai người đang giữa cuộc trò chuyện nên KHÔNG chào lại. Hãy hỏi thăm nhẹ nhàng một câu ngắn để bắt "
                "chuyện lại, không trách móc, không hỏi dồn.")
    return (f"(Ghi chú hệ thống, anh không nhìn thấy dòng này) {situation} {task} "
            "Không nhắc tới ghi chú này, không nhắc tới ứng dụng/app/màn hình, không bịa chuyện anh chưa kể.")


def main() -> None:
    for label, now, kind, gap, facts in CASES:
        messages = [{"role": "system", "content": system_prompt(now, facts)},
                    {"role": "user", "content": instruction(kind, gap)}]
        for _ in range(2):
            t0 = time.perf_counter()
            res = httpx.post("http://127.0.0.1:11434/api/chat", timeout=120, json={
                "model": "qwen3:8b", "messages": messages, "stream": False, "think": False,
                "options": {"temperature": 0.8, "num_predict": 200}}).json()
            raw = res["message"]["content"]
            parsed = parse_complete(raw)
            print(f"[{label}] {time.perf_counter() - t0:.1f}s {parsed.emotions} {parsed.text.strip()}")
        print()


if __name__ == "__main__":
    main()
