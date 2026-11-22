"""Mẫu nghe giọng VOICEVOX (engine chạy riêng ở 127.0.0.1:50021) + lưu nguyên văn điều khoản của từng giọng.

Ra spikes/audio/out/voicevox/ (không vào git). Chạy: uv run python spikes/audio/voicevox_samples.py
"""

import json
from pathlib import Path

import httpx

URL = "http://127.0.0.1:50021"
OUT = Path("spikes/audio/out/voicevox")
TEXT = "おかえり！今日はどうだった？ずっと待ってたんだよ。"
# (tên, style id) — giọng nữ trẻ, hợp kiểu "anime dễ thương"
VOICES = [("四国めたん", 2), ("ずんだもん", 3), ("春日部つむぎ", 8), ("雨晴はう", 10), ("冥鳴ひまり", 14),
          ("WhiteCUL", 23), ("櫻歌ミコ", 43), ("小夜", 46), ("猫使ビィ", 58), ("東北ずん子", 107)]

OUT.mkdir(parents=True, exist_ok=True)
speakers = {s["name"].split("/")[0]: s["speaker_uuid"] for s in httpx.get(f"{URL}/speakers").json()}
with httpx.Client(base_url=URL, timeout=60) as c:
    for i, (name, style) in enumerate(VOICES, 1):
        query = c.post("/audio_query", params={"text": TEXT, "speaker": style}).json()
        wav = c.post("/synthesis", params={"speaker": style}, json=query).content
        (OUT / f"{i:02d}_{name}.wav").write_bytes(wav)
        info = c.get("/speaker_info", params={"speaker_uuid": speakers[name]}).json()
        (OUT / f"{i:02d}_{name}_policy.md").write_text(info.get("policy", ""), encoding="utf-8")
        print("xong", i, name, len(wav) // 1024, "KB")
print(json.dumps([n for n, _ in VOICES], ensure_ascii=False))
