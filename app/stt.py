"""Nhận dạng giọng nói (STT). Mọi engine theo hợp đồng SpeechRecognizer, chọn bằng STT_PROVIDER.

transcribe() chạy đồng bộ (CPU) nên server gọi qua asyncio.to_thread. Âm thanh chỉ nằm trong RAM.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_RATE = 16000


class STTError(Exception):
    """Lỗi đã có câu tiếng Việt, hiển thị thẳng cho người dùng."""


class SpeechRecognizer(Protocol):
    name: str

    def transcribe(self, pcm16: bytes) -> str:
        """PCM 16-bit LE mono 16kHz -> chữ ("" nếu không có tiếng nói)."""
        ...

    def check(self) -> str | None:
        ...

    def warm_up(self) -> None:
        ...

    def info(self) -> dict:
        """Thông tin cho /api/health (model, thiết bị)."""
        ...


# Câu Whisper hay "bịa" khi chỉ có tiếng ồn (học từ phụ đề YouTube tiếng Việt)
HALLUCINATIONS = ("subscribe", "ghiền mì gõ", "cảm ơn các bạn đã theo dõi", "hẹn gặp lại các bạn", "like và share")


def keep_segment(no_speech_prob: float, avg_logprob: float, compression_ratio: float, text: str = "") -> bool:
    """Đo thật (spikes/audio/bench_stt.py): tiếng ồn/ù cho câu bịa "Hãy subscribe cho kênh..." với
    no_speech_prob 0,89-0,93 nhưng avg_logprob lại cao (-0,28), còn câu nói thật có no_speech_prob ≤ 0,58.
    Nên dựa chủ yếu vào no_speech_prob, cộng danh sách câu bịa quen thuộc."""
    if no_speech_prob > 0.8:
        return False
    if no_speech_prob > 0.6 and avg_logprob < -0.7:
        return False
    if compression_ratio > 2.4:  # lặp đi lặp lại
        return False
    if any(h in text.lower() for h in HALLUCINATIONS):
        return False
    return avg_logprob > -1.2


class WhisperSTT:
    name = "whisper"

    def __init__(self) -> None:
        self.model_name = os.getenv("WHISPER_MODEL", "small").strip()
        self.device = os.getenv("WHISPER_DEVICE", "cpu").strip().lower()
        default_compute = "int8" if self.device == "cpu" else "float16"
        self.compute_type = os.getenv("WHISPER_COMPUTE", default_compute).strip().lower()
        # Đo trên i7-14650HX: 12 luồng 1,25s/câu, mặc định (0) 1,51s, 16 luồng không nhanh thêm
        self.threads = int(os.getenv("WHISPER_THREADS", str(min(12, os.cpu_count() or 4))))
        self._model = None
        self._lock = threading.Lock()

    def info(self) -> dict:
        return {"model": self.model_name, "device": self.device}

    def check(self) -> str | None:
        import importlib.util

        if importlib.util.find_spec("faster_whisper") is None:
            return "Chưa cài thư viện nghe giọng nói. Chạy: uv sync"
        return None

    def _load(self):
        with self._lock:
            if self._model is None:
                problem = self.check()
                if problem:
                    raise STTError(problem)
                from faster_whisper import WhisperModel  # nạp lười: lần đầu còn tải model (~0,5GB)

                try:
                    self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type,
                                               cpu_threads=self.threads)
                except Exception as err:
                    raise STTError(f"Không nạp được Whisper '{self.model_name}' trên {self.device}: {err}") from err
            return self._model

    def warm_up(self) -> None:
        model = self._load()
        silence = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        with self._lock:
            list(model.transcribe(silence, language="vi", beam_size=1)[0])

    def transcribe(self, pcm16: bytes) -> str:
        model = self._load()
        audio = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
        with self._lock:
            segments, _ = model.transcribe(
                audio,
                language="vi",
                beam_size=1,
                vad_filter=True,  # Silero VAD có sẵn: cắt im lặng đầu/cuối, bỏ đoạn không có tiếng nói
                condition_on_previous_text=False,  # tránh lặp câu
                without_timestamps=True,
            )
            texts = [s.text.strip() for s in segments
                     if keep_segment(s.no_speech_prob, s.avg_logprob, s.compression_ratio, s.text)]
        return " ".join(t for t in texts if t).strip()


ZIPFORMER_FILES = {
    "encoder": "encoder-epoch-20-avg-10.int8.onnx",
    "decoder": "decoder-epoch-20-avg-10.int8.onnx",
    "joiner": "joiner-epoch-20-avg-10.int8.onnx",
    "tokens": "config.json",  # file token của model này đặt tên là config.json
    "bpe_vocab": "bpe.model",
}


def speech_only(audio: np.ndarray) -> np.ndarray:
    """Giữ đoạn từ lúc bắt đầu tới lúc hết tiếng nói (Silero VAD có sẵn trong faster-whisper); không có tiếng nói
    thì trả mảng rỗng. Đo thật: không có bước này, Zipformer đọc im lặng/tiếng ồn thành "Và", "Đây", "Tôi"."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    spans = get_speech_timestamps(
        audio, VadOptions(min_speech_duration_ms=200, min_silence_duration_ms=500, speech_pad_ms=200)
    )
    if not spans:
        return audio[:0]
    return audio[spans[0]["start"]:spans[-1]["end"]]


def normalize_transcript(text: str) -> str:
    """Zipformer trả chữ IN HOA không dấu câu ("CHÀO EM HÔM NAY") -> "Chào em hôm nay"."""
    text = " ".join(text.split()).lower()
    return text[:1].upper() + text[1:]


class ZipformerSTT:
    """Zipformer-30M-RNNT-6000h (tiếng Việt) qua sherpa-onnx, CPU int8.

    Học từ dự án VoiceDeck. Đo trên giọng người thật (FLEURS): sai 9,2% từ, 0,27s/câu, so với Whisper small 23,2%
    và 2,68s (spikes/audio/KET_QUA.md). Là RNN-Transducer nên không "bịa" câu khi im lặng như Whisper.
    """

    name = "zipformer"

    def __init__(self) -> None:
        path = Path(os.getenv("ZIPFORMER_DIR", "models/zipformer"))
        self.model_dir = path if path.is_absolute() else ROOT / path
        self.threads = int(os.getenv("ZIPFORMER_THREADS", "8"))  # VoiceDeck đo: 8 luồng nhanh nhất
        self._recognizer = None
        self._lock = threading.Lock()

    def info(self) -> dict:
        return {"model": "zipformer-30m", "device": "cpu"}

    def check(self) -> str | None:
        import importlib.util

        if importlib.util.find_spec("sherpa_onnx") is None:
            return "Chưa cài thư viện nghe giọng nói (sherpa-onnx). Chạy: uv sync"
        missing = [f for f in ZIPFORMER_FILES.values() if not (self.model_dir / f).exists()]
        if missing:
            return (f"Chưa có model nghe giọng nói ở {self.model_dir} (thiếu {', '.join(missing)}). "
                    "Chạy: uv run python scripts/get_stt_model.py, hoặc đặt ZIPFORMER_DIR trong .env")
        return None

    def _load(self):
        with self._lock:
            if self._recognizer is None:
                problem = self.check()
                if problem:
                    raise STTError(problem)
                import sherpa_onnx

                files = {k: str(self.model_dir / v) for k, v in ZIPFORMER_FILES.items()}
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    **files, modeling_unit="bpe", num_threads=self.threads, sample_rate=SAMPLE_RATE, provider="cpu",
                )
            return self._recognizer

    def warm_up(self) -> None:
        self.transcribe(bytes(SAMPLE_RATE))  # 0,5s im lặng: nạp model và chạy thử một lần

    def transcribe(self, pcm16: bytes) -> str:
        recognizer = self._load()
        audio = speech_only(np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0)
        if audio.size == 0:
            return ""
        stream = recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, audio)
        with self._lock:
            recognizer.decode_stream(stream)
        return normalize_transcript(stream.result.text)


def make_stt() -> SpeechRecognizer | None:
    provider = os.getenv("STT_PROVIDER", "zipformer").strip().lower()
    if provider == "zipformer":
        return ZipformerSTT()
    if provider == "whisper":
        return WhisperSTT()
    if provider in ("none", "off", ""):
        return None
    raise ValueError(f"STT_PROVIDER không hợp lệ: {provider!r} (dùng 'zipformer', 'whisper' hoặc 'none')")
