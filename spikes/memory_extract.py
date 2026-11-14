"""Spike trí nhớ: đo token thật (prompt_eval_count của Ollama) và thử prompt trích xuất "điều đáng nhớ" bằng qwen3:8b.

Lần 1 (cho model tự liệt kê điều "outdated" để xóa): model 8B xóa bừa cả điều không liên quan -> bỏ.
Lần 2 (bản này): model chỉ gán LOẠI từ danh sách cố định; code tự thay điều cũ cùng loại nếu loại chỉ có một giá trị.

uv run python spikes/memory_extract.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.persona import SYSTEM_PROMPT  # noqa: E402

URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:8b"
SINGLE = {"ten", "tuoi", "nghe_nghiep", "noi_o", "cach_goi"}  # mỗi loại chỉ giữ điều mới nhất
KINDS = "ten, tuoi, nghe_nghiep, noi_o, cach_goi, gia_dinh, thu_cung, so_thich, khong_thich, suc_khoe, su_kien, khac"

EXTRACT = """Bạn là bộ nhớ của một nhân vật AI tên Mira. Đọc tin nhắn mới nhất của người dùng (anh) và chọn ra những
thông tin ĐÁNG NHỚ LÂU DÀI về anh.

Quy tắc:
- Chỉ lấy điều anh tự nói về bản thân. Không lấy điều Mira nói, không suy đoán, không bịa.
- Bỏ qua chào hỏi, câu hỏi, cảm xúc thoáng qua.
- Mỗi ý là một câu ngắn ở ngôi thứ ba, bắt đầu bằng "Anh", vd "Anh tên là Khoa".
- Gán đúng một loại: {kinds}.
- Hôm nay là {today}. Đổi mốc thời gian tương đối ("tuần sau", "hôm qua") thành ngày cụ thể dd/mm/yyyy.
- Không lặp lại điều đã có trong ĐÃ BIẾT. Không có gì đáng nhớ thì trả về danh sách rỗng.

ĐÃ BIẾT:
{known}

TIN NHẮN MỚI CỦA ANH:
{message}

Trả về JSON đúng dạng: {{"facts": [{{"loai": "...", "noi_dung": "..."}}]}}"""

CASES = [
    ("Chào em, hôm nay em thế nào?", []),
    ("Anh tên là Khoa, năm nay 24 tuổi, đang làm lập trình viên ở Đà Nẵng.", ["Khoa", "24", "lập trình", "Đà Nẵng"]),
    ("Anh nuôi một con mèo tên Mướp, nó lười lắm.", ["Mướp"]),
    ("Em thích ăn món gì nhất?", []),
    ("Anh ghét ăn hành, với lại anh dị ứng hải sản nha.", ["hành", "hải sản"]),
    ("Thứ bảy tuần sau anh đi phỏng vấn ở FPT đó.", ["FPT", "21/11"]),
    ("Thôi anh đi ngủ đây, mai nói chuyện tiếp nha.", []),
    ("À anh chuyển vào Sài Gòn sống rồi nhé.", ["Sài Gòn"]),
    ("Em gọi anh là Khoa thôi, đừng gọi anh nữa nghe kỳ.", ["Khoa"]),
]


def call(messages, fmt=None):
    payload = {"model": MODEL, "messages": messages, "stream": False, "think": False, "keep_alive": "30m",
               "options": {"temperature": 0.2, "num_predict": 256}}
    if fmt:
        payload["format"] = fmt
    t0 = time.perf_counter()
    res = httpx.post(URL, json=payload, timeout=120).json()
    return res, time.perf_counter() - t0


def main() -> None:
    res, _ = call([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "Chào em"}])
    print(f"Token: system prompt + 'Chào em' = {res['prompt_eval_count']}")

    known: list[dict] = []
    ok = 0
    times = []
    for message, expect in CASES:
        prompt = EXTRACT.format(kinds=KINDS, today="thứ Sáu, 14/11/2026", message=message,
                                known="\n".join(f"- [{k['loai']}] {k['noi_dung']}" for k in known) or "(chưa có)")
        res, took = call([{"role": "user", "content": prompt}], fmt="json")
        times.append(took)
        try:
            facts = [f for f in json.loads(res["message"]["content"]).get("facts", [])
                     if isinstance(f, dict) and f.get("noi_dung")]
        except (json.JSONDecodeError, AttributeError):
            facts = []
            print("   JSON hỏng:", res["message"]["content"][:80])
        text = " ".join(f["noi_dung"] for f in facts).lower()
        good = all(k.lower() in text for k in expect) and (bool(facts) == bool(expect))
        ok += good
        print(f"{'OK ' if good else 'SAI'} {took:.1f}s | {message}\n      → {[(f.get('loai'), f['noi_dung']) for f in facts]}")
        for f in facts:  # luật do code quyết định
            if f.get("loai") in SINGLE:
                known = [k for k in known if k["loai"] != f["loai"]]
            known.append(f)
    print(f"\nĐúng {ok}/{len(CASES)} | thời gian trích xuất trung vị {sorted(times)[len(times) // 2]:.2f}s")
    print("ĐÃ BIẾT cuối cùng:")
    for k in known:
        print(f"  [{k['loai']}] {k['noi_dung']}")


if __name__ == "__main__":
    main()
