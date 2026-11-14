"""Tải model nhận dạng giọng nói Zipformer-30M (tiếng Việt) vào models/zipformer/ (không đưa vào git).

uv run python scripts/get_stt_model.py

Model: hynt/Zipformer-30M-RNNT-6000h, license CC-BY-NC-ND-4.0 (chỉ dùng cá nhân, phi thương mại).
Máy đã có sẵn model (vd từ dự án VoiceDeck) thì không cần tải: đặt ZIPFORMER_DIR trong .env trỏ tới thư mục đó.
"""

from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://huggingface.co/hynt/Zipformer-30M-RNNT-6000h/resolve/main"
FILES = [
    "encoder-epoch-20-avg-10.int8.onnx",
    "decoder-epoch-20-avg-10.int8.onnx",
    "joiner-epoch-20-avg-10.int8.onnx",
    "config.json",  # thực chất là bảng token
    "bpe.model",
]


def main() -> None:
    out = ROOT / "models" / "zipformer"
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = out / name
        if dest.exists():
            print(f"đã có {dest.relative_to(ROOT)}")
            continue
        print(f"tải {name}")
        with httpx.stream("GET", f"{BASE}/{name}", follow_redirects=True, timeout=300) as res:
            res.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as f:
                for chunk in res.iter_bytes():
                    f.write(chunk)
            tmp.replace(dest)
    print("xong. Model nằm trong models/zipformer/")


if __name__ == "__main__":
    main()
