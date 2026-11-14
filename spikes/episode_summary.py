"""Spike spec 009: qwen3:8b tóm tắt một buổi trò chuyện có trung thực không (không bịa, giữ việc hẹn/ngày)."""

import asyncio
import json
import sys
import time

from dotenv import load_dotenv

load_dotenv(".env")
sys.path.insert(0, ".")
from app.episodes import summary_messages  # noqa: E402
from app.llm import make_llm  # noqa: E402

SESSIONS = {
    "phong_van": [
        ("user", "Hôm nay anh mệt quá, sếp bắt làm thêm giờ."),
        ("assistant", "Thương anh ghê, anh nghỉ ngơi chút đi nha."),
        ("user", "Ừ, mà thứ Sáu này anh đi phỏng vấn ở FPT đó, hơi run."),
        ("assistant", "Anh giỏi mà, em tin anh làm được! Anh ứng tuyển vị trí gì vậy?"),
        ("user", "Lập trình viên backend. Anh đang ôn Python với SQL."),
        ("assistant", "Hay quá! Cố lên anh nha."),
    ],
    "meo_om": [
        ("user", "Con mèo Mướp nhà anh bị ốm, bỏ ăn từ hôm qua."),
        ("assistant", "Ôi, tội Mướp quá. Anh đưa bé đi khám chưa?"),
        ("user", "Chưa, mai anh định đưa đi thú y gần nhà."),
        ("assistant", "Vậy mai anh nhớ đưa bé đi sớm nha, em lo cho Mướp quá."),
    ],
    "chuyen_phiem": [
        ("user", "Em thích mùa nào nhất?"),
        ("assistant", "Em thích mùa thu nhất, có nắng vàng với lá rơi. Còn anh?"),
        ("user", "Anh thích mùa đông, được ngủ nướng."),
        ("assistant", "Haha, anh lười ghê! Nhưng em cũng thích được cuộn chăn."),
    ],
}


async def main():
    llm = make_llm()
    await llm.warm_up()
    for name, turns in SESSIONS.items():
        for k in range(3):
            t = time.perf_counter()
            raw = await llm.complete(summary_messages(turns), json_mode=True, max_tokens=300)
            print(f"{name} #{k} {time.perf_counter() - t:.1f}s: {json.loads(raw).get('tom_tat')}", flush=True)


asyncio.run(main())
