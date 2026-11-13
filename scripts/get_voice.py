"""Tải giọng Piper tiếng Việt vào models/piper/ (không đưa vào git).

uv run python scripts/get_voice.py [tên_giọng]

Mặc định: vi_VN-vais1000-medium (dataset VAIS-1000, CC-BY-4.0). Giọng 25hours_single bị mất dấu thanh với
piper-tts 1.8 nên không dùng (xem spikes/audio/KET_QUA.md).
"""

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN"
VOICES = {"vi_VN-vais1000-medium": "vais1000/medium"}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "vi_VN-vais1000-medium"
    if name not in VOICES:
        sys.exit(f"Chưa hỗ trợ giọng {name!r}. Có: {', '.join(VOICES)}")
    out = ROOT / "models" / "piper"
    out.mkdir(parents=True, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        dest = out / f"{name}{ext}"
        if dest.exists():
            print(f"đã có {dest.relative_to(ROOT)}")
            continue
        url = f"{BASE}/{VOICES[name]}/{name}{ext}"
        print(f"tải {url}")
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as res:
            res.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with tmp.open("wb") as f:
                for chunk in res.iter_bytes():
                    f.write(chunk)
            tmp.replace(dest)
    print("xong. Giọng nằm trong models/piper/")


if __name__ == "__main__":
    main()
