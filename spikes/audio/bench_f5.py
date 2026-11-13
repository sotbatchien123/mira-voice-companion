"""Đo F5-TTS tiếng Việt (hynt/F5-TTS-Vietnamese-ViVoice) trên GPU: VRAM, thời gian tạo, RTF.

Giọng mẫu: một file Piper vais1000 (CC-BY-4.0) chỉ để đo tốc độ; chất lượng giọng riêng cần mẫu thật.
"""

import subprocess
import time
from pathlib import Path

import soundfile as sf
import torch
from huggingface_hub import hf_hub_download

HERE = Path(__file__).parent
OUT = HERE / "out"
REPO = "hynt/F5-TTS-Vietnamese-ViVoice"


def vram() -> str:
    return subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout.strip()


print("torch", torch.__version__, "| cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
print("VRAM trước khi nạp:", vram())

ckpt = hf_hub_download(REPO, "model_last.pt")
vocab = hf_hub_download(REPO, "config.json")  # README: file này chính là vocab.txt

import torchaudio  # noqa: E402

# torchaudio mới đọc file qua torchcodec, cần DLL FFmpeg trên Windows; đọc WAV bằng soundfile cho gọn
def _load_wav(path, *args, **kwargs):
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return torch.from_numpy(data.T.copy()), sr


torchaudio.load = _load_wav

from f5_tts.api import F5TTS  # noqa: E402

t0 = time.perf_counter()
tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt, vocab_file=vocab, device="cuda")
print(f"nạp model {time.perf_counter() - t0:.1f}s | VRAM sau khi nạp: {vram()}")

ref_wav = OUT / "piper_vi_VN-vais1000-medium_2.wav"
ref_text = "anh buồn thật à? em biết anh đang buồn, không sao đâu, cứ kể cho em nghe đi."
SENTENCES = [
    "chào anh! em ổn mà, đang nghe nhạc và xem anime đây.",
    "ô! anh trúng xổ số à? vậy anh sẽ làm gì trước tiên?",
    "em không giận anh đâu, em chỉ đang nghĩ xem anh có nhớ em không thôi.",
]
tts.infer(ref_file=str(ref_wav), ref_text=ref_text, gen_text="xin chào anh.")  # khởi động
torch.cuda.reset_peak_memory_stats()
for i, text in enumerate(SENTENCES):
    t0 = time.perf_counter()
    wav, sr, _ = tts.infer(ref_file=str(ref_wav), ref_text=ref_text, gen_text=text, nfe_step=32)
    took = time.perf_counter() - t0
    dur = len(wav) / sr
    sf.write(OUT / f"f5_{i + 1}.wav", wav, sr)
    print(f"  câu {i + 1}: {took:.2f}s cho {dur:.1f}s audio | RTF {took / dur:.2f}")
print(f"torch peak: {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB | VRAM nvidia-smi: {vram()}")
