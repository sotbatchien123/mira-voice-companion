"""Engine giọng nói. Mọi engine theo cùng hợp đồng SpeechEngine, nên đổi engine chỉ là đổi TTS_PROVIDER.

stream() chạy đồng bộ (CPU) và trả từng mảnh PCM ngay khi tạo ra; server chạy nó trong thread riêng.
"""

from __future__ import annotations

import importlib.util
import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PIPER_VOICE = "models/piper/vi_VN-vais1000-medium.onnx"
DEFAULT_VIENEU_VOICE = "Mỹ Duyên"


class TTSError(Exception):
    """Lỗi đã có câu tiếng Việt, hiển thị thẳng cho người dùng."""


class SpeechEngine(Protocol):
    name: str
    sample_rate: int  # đúng sau khi đã nạp model (warm_up hoặc mảnh đầu tiên)
    segment_pause_s: float  # khoảng nghỉ server chèn thêm sau mỗi đoạn

    def stream(self, text: str) -> Iterator[bytes]:
        """Từng mảnh PCM 16-bit little-endian, mono."""
        ...

    def check(self) -> str | None:
        """None nếu sẵn sàng, ngược lại là câu tiếng Việt nói cách khắc phục."""
        ...

    def warm_up(self) -> None:
        """Nạp model trước để lượt chat đầu không bị chậm."""
        ...


def float_to_pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()


class PiperTTS:
    name = "piper"
    segment_pause_s = 0.25  # Piper gần như không có lặng cuối câu, nghe dính liền nếu không chèn

    def __init__(self, voice_path: str | Path | None = None) -> None:
        path = Path(voice_path or os.getenv("PIPER_VOICE", DEFAULT_PIPER_VOICE))
        self.voice_path = path if path.is_absolute() else ROOT / path
        self.length_scale = float(os.getenv("PIPER_LENGTH_SCALE", "1.0"))
        self.sample_rate = 22050
        self._voice = None
        self._lock = threading.Lock()

    def check(self) -> str | None:
        if not self.voice_path.exists() or not self.voice_path.with_suffix(".onnx.json").exists():
            return f"Chưa có file giọng {self.voice_path.name}. Chạy: uv run python scripts/get_voice.py"
        return None

    def _load(self):
        with self._lock:
            if self._voice is None:
                problem = self.check()
                if problem:
                    raise TTSError(problem)
                from piper import PiperVoice  # nạp lười: import onnxruntime mất thời gian

                self._voice = PiperVoice.load(self.voice_path)
                self.sample_rate = self._voice.config.sample_rate
            return self._voice

    def warm_up(self) -> None:
        if self.check() is None:
            self._load()

    def stream(self, text: str) -> Iterator[bytes]:
        from piper import SynthesisConfig

        voice = self._load()
        for chunk in voice.synthesize(text, syn_config=SynthesisConfig(length_scale=self.length_scale)):
            yield chunk.audio_int16_bytes


class VieNeuTTS:
    """VieNeu-TTS v3 Turbo (Apache-2.0) chạy CPU qua ONNX Runtime, stream từng mảnh ~0,32s."""

    name = "vieneu"
    supports_cues = True  # hiểu "[cười]", "[thở dài]", "[hắng giọng]" thành tiếng thật
    segment_pause_s = 0.0  # mỗi câu đã có sẵn ~0,24-0,37s lặng ở cuối

    def __init__(self) -> None:
        self.voice = os.getenv("VIENEU_VOICE", DEFAULT_VIENEU_VOICE).strip()
        self.precision = os.getenv("VIENEU_PRECISION", "fp32").strip().lower()
        self.temperature = float(os.getenv("VIENEU_TEMPERATURE", "0.8"))
        self.sample_rate = 48000
        self._tts = None
        self._lock = threading.Lock()  # một model dùng chung, mỗi lúc chỉ tạo một câu

    def check(self) -> str | None:
        if importlib.util.find_spec("vieneu") is None:
            return "Chưa cài thư viện giọng VieNeu. Chạy: uv sync"
        return None

    def _load(self):
        with self._lock:
            if self._tts is None:
                problem = self.check()
                if problem:
                    raise TTSError(problem)
                from vieneu import Vieneu  # nạp lười: lần đầu còn tải model từ Hugging Face

                tts = Vieneu() if self.precision == "fp32" else Vieneu(precision=self.precision)
                voices = {voice_id for _, voice_id in tts.list_preset_voices()}
                if self.voice not in voices:
                    raise TTSError(f"VieNeu không có giọng '{self.voice}'. Có: {', '.join(sorted(voices))}")
                self.sample_rate = int(getattr(tts, "sample_rate", 48000))
                self._tts = tts
            return self._tts

    def warm_up(self) -> None:
        tts = self._load()
        with self._lock:
            tts.infer("Xin chào.", voice=self.voice)  # lần chạy đầu của ONNX Runtime chậm hơn hẳn

    def stream(self, text: str) -> Iterator[bytes]:
        tts = self._load()
        with self._lock:
            for chunk in tts.infer_stream(text, voice=self.voice, temperature=self.temperature):
                yield float_to_pcm16(chunk)


def make_tts() -> SpeechEngine | None:
    provider = os.getenv("TTS_PROVIDER", "vieneu").strip().lower()
    if provider == "vieneu":
        return VieNeuTTS()
    if provider == "piper":
        return PiperTTS()
    if provider in ("none", "off", ""):
        return None
    raise ValueError(f"TTS_PROVIDER không hợp lệ: {provider!r} (dùng 'vieneu', 'piper' hoặc 'none')")
