"""Các "bộ não" của nhân vật. Mọi LLM tuân theo cùng hợp đồng ChatLLM.stream(),
nên đổi Claude <-> model local không phải sửa server hay frontend.

Chọn bằng biến môi trường LLM_PROVIDER = ollama (mặc định) | claude (xem make_llm).
Mỗi provider tự đổi lỗi của mình thành LLMError có câu tiếng Việt.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Literal, Protocol

import anthropic
import httpx

from .persona import SYSTEM_PROMPT

Event = tuple[Literal["text", "stop"], str]


class LLMError(Exception):
    """Lỗi đã có sẵn câu giải thích thân thiện, hiển thị thẳng cho người dùng."""


class ChatLLM(Protocol):
    provider: str
    model: str

    def stream(self, history: list[dict[str, str]], system: str | None = None) -> AsyncIterator[Event]:
        """Phát ("text", delta) cho từng mảnh text, cuối cùng ("stop", stop_reason).

        `system`: system prompt do server dựng (persona + ngày giờ + trí nhớ); None thì dùng persona gốc."""
        ...

    async def complete(self, messages: list[dict[str, str]], *, json_mode: bool = False, max_tokens: int = 256) -> str:
        """Lời gọi ngắn, không stream (vd trích xuất trí nhớ). json_mode: ép trả JSON nếu provider hỗ trợ."""
        ...

    async def check(self) -> str | None:
        """Kiểm tra nhanh, không tốn tiền: None nếu sẵn sàng, ngược lại là câu tiếng Việt nói cách khắc phục."""
        ...

    async def warm_up(self) -> None:
        """Chuẩn bị trước để câu trả lời đầu không chậm (vd nạp model vào GPU). Không tốn tiền."""
        ...


class ClaudeLLM:
    provider = "claude"

    def __init__(self) -> None:
        self.model = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
        self.effort = os.getenv("CLAUDE_EFFORT", "low")
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        # Tạo lười: thiếu key thì lỗi rơi vào request, được báo thành câu dễ hiểu cho người dùng
        if self._client is None:
            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def warm_up(self) -> None:
        pass  # API cloud luôn sẵn sàng; không gọi thử để khỏi tốn tiền

    async def check(self) -> str | None:
        # Chỉ xem có key chưa; không gọi API để mở trang không tốn tiền
        if self._client is None and not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            return "Chưa có ANTHROPIC_API_KEY. Điền key vào file .env rồi khởi động lại server."
        return None

    async def stream(self, history: list[dict[str, str]], system: str | None = None) -> AsyncIterator[Event]:
        try:
            async with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=2048,  # câu trả lời chat ngắn; tránh nhân vật nói quá dài
                system=system or SYSTEM_PROMPT,
                output_config={"effort": self.effort},
                # Model chính từ chối vì bộ lọc an toàn -> API tự chuyển sang model dự phòng phù hợp
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=history,
            ) as stream:
                async for text in stream.text_stream:
                    yield ("text", text)
                final = await stream.get_final_message()
                yield ("stop", final.stop_reason or "")
        except Exception as err:
            _raise_friendly_claude_error(err)

    async def complete(self, messages: list[dict[str, str]], *, json_mode: bool = False, max_tokens: int = 256) -> str:
        # Claude không có cờ ép JSON ở đây: prompt của bên gọi đã yêu cầu JSON, bên gọi tự parse an toàn
        try:
            res = await self.client.messages.create(model=self.model, max_tokens=max_tokens, messages=messages,
                                                    output_config={"effort": "low"})
        except Exception as err:
            _raise_friendly_claude_error(err)
        return "".join(b.text for b in res.content if getattr(b, "type", "") == "text")


def _raise_friendly_claude_error(err: Exception) -> None:
    """Đổi lỗi của SDK Claude thành LLMError có câu tiếng Việt; lỗi lạ thì để nguyên."""
    if isinstance(err, anthropic.AuthenticationError):
        raise LLMError("Sai ANTHROPIC_API_KEY. Kiểm tra lại file .env nhé.") from err
    if isinstance(err, anthropic.RateLimitError):
        raise LLMError("Claude đang bị giới hạn tốc độ (429), thử lại sau ít giây nhé.") from err
    if isinstance(err, anthropic.APIStatusError):
        raise LLMError(f"Claude API lỗi {err.status_code}: {err.message}") from err
    if isinstance(err, anthropic.APIConnectionError):
        raise LLMError("Không kết nối được tới Claude API (kiểm tra mạng).") from err
    # SDK báo TypeError này trước khi gửi request khi không tìm thấy key nào
    if isinstance(err, TypeError) and "authentication method" in str(err):
        raise LLMError("Chưa có ANTHROPIC_API_KEY. Điền key vào file .env rồi khởi động lại server.") from err
    raise err


class OllamaLLM:
    """Model chạy local qua Ollama (https://ollama.com), dùng API gốc /api/chat dạng NDJSON stream."""

    provider = "ollama"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.base_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        # Giữ model trong VRAM một lúc để câu sau không phải nạp lại (nạp lại mất vài giây)
        self.keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
        # Model có chế độ "suy nghĩ" (vd Qwen 3): tắt đi để trả lời nhanh. Để trống = không gửi tham số
        self.think = os.getenv("OLLAMA_THINK", "").strip().lower()
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.8"))
        self._transport = transport  # test truyền transport giả vào đây

    def _payload(self, history: list[dict[str, str]], system: str | None = None) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system or SYSTEM_PROMPT}, *history],
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {"temperature": self.temperature, "num_predict": 512},
        }
        if self.think in ("true", "false"):
            payload["think"] = self.think == "true"
        return payload

    async def stream(self, history: list[dict[str, str]], system: str | None = None) -> AsyncIterator[Event]:
        # connect ngắn để báo nhanh khi Ollama chưa bật; read dài vì lần đầu nạp model vào GPU khá lâu
        timeout = httpx.Timeout(120.0, connect=3.0)
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=self._transport) as client:
                async with client.stream("POST", "/api/chat", json=self._payload(history, system)) as res:
                    if res.status_code != 200:
                        await res.aread()
                        raise LLMError(self._http_error(res))
                    stop = ""
                    async for line in res.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        if "error" in data:
                            raise LLMError(f"Ollama báo lỗi: {data['error']}")
                        text = data.get("message", {}).get("content", "")
                        if text:
                            yield ("text", text)
                        if data.get("done"):
                            stop = data.get("done_reason", "stop")
                            break
                    # Chuẩn hóa về tên stop_reason giống Claude để server xử lý chung
                    yield ("stop", {"stop": "end_turn", "length": "max_tokens"}.get(stop, stop))
        except httpx.ConnectError as err:
            raise LLMError(
                f"Không kết nối được Ollama ở {self.base_url}. Đã cài và mở Ollama chưa?"
            ) from err
        except httpx.TimeoutException as err:
            raise LLMError("Ollama phản hồi quá lâu (model quá nặng cho GPU, hoặc đang nạp lần đầu).") from err
        except httpx.HTTPError as err:
            raise LLMError(f"Mất kết nối với Ollama giữa chừng ({type(err).__name__}). Ollama còn chạy không?") from err

    async def warm_up(self) -> None:
        """Nạp model vào GPU trước: sau OLLAMA_KEEP_ALIVE (mặc định 30 phút) không dùng, Ollama nhả model ra và câu
        đầu tiên phải chờ ~9s để nạp lại. /api/generate không kèm prompt chỉ nạp model, không sinh chữ."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(120.0, connect=3.0), transport=self._transport) as client:
            res = await client.post("/api/generate", json={"model": self.model, "keep_alive": self.keep_alive})
            res.raise_for_status()

    async def complete(self, messages: list[dict[str, str]], *, json_mode: bool = False, max_tokens: int = 256) -> str:
        payload: dict = {
            "model": self.model, "messages": messages, "stream": False, "keep_alive": self.keep_alive,
            # nhiệt độ thấp: trích xuất cần ổn định, không cần sáng tạo
            "options": {"temperature": 0.2, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        if self.think in ("true", "false"):
            payload["think"] = self.think == "true"
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(60.0, connect=3.0), transport=self._transport) as client:
                res = await client.post("/api/chat", json=payload)
        except httpx.HTTPError as err:
            raise LLMError(f"Không gọi được Ollama ({type(err).__name__}).") from err
        if res.status_code != 200:
            raise LLMError(self._http_error(res))
        return res.json().get("message", {}).get("content", "")

    async def check(self) -> str | None:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(5.0, connect=3.0), transport=self._transport) as client:
                res = await client.get("/api/tags")
                res.raise_for_status()
        except httpx.HTTPError:
            return f"Không kết nối được Ollama ở {self.base_url}. Mở Ollama (hoặc chạy: ollama serve) rồi tải lại trang."
        names = {m.get("name") for m in res.json().get("models", [])}
        # "qwen3" và "qwen3:latest" là cùng một model
        if self.model not in names and f"{self.model}:latest" not in names:
            return f"Ollama chưa có model '{self.model}'. Chạy: ollama pull {self.model}"
        return None

    def _http_error(self, res: httpx.Response) -> str:
        try:
            detail = res.json().get("error", res.text)
        except ValueError:
            detail = res.text
        if res.status_code == 404:
            return f"Ollama chưa có model '{self.model}'. Chạy: ollama pull {self.model}"
        return f"Ollama lỗi {res.status_code}: {detail}"


def make_llm() -> ChatLLM:
    # Mặc định local (constitution III): thiếu .env vẫn chạy được mà không cần key
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider == "claude":
        return ClaudeLLM()
    if provider == "ollama":
        return OllamaLLM()
    raise ValueError(f"LLM_PROVIDER không hợp lệ: {provider!r} (dùng 'claude' hoặc 'ollama')")
