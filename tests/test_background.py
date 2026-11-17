"""Lỗi 4 (code review 2026-11-15): việc chạy nền sau lượt chat không được mất khi anh ngắt lời Mira.

Ngắt lời = trình duyệt đóng kết nối SSE -> server hủy task `produce`. Trước đây `produce` đang `await extra` (ghi nhớ,
ghi buổi trò chuyện) nên asyncio hủy luôn cả `extra`: anh càng hay ngắt lời, Mira càng quên.
"""

import asyncio
import gc
import json
import weakref
from datetime import datetime

from app.main import reply_stream, schedule_episode_close
from app.episodes import EpisodeStore
from app.turn_log import TurnLog


class FakeLLM:
    provider, model = "fake", "fake-model"

    async def stream(self, history, system=None):
        yield ("text", "[happy] Dạ anh!")
        yield ("stop", "end_turn")


def test_ngat_loi_khong_huy_viec_ghi_nho(tmp_path):
    done = []

    async def run():
        gate = asyncio.Event()

        async def after_text(raw):
            await gate.wait()  # ghi nhớ đang gọi model (chậm hơn lúc anh ngắt lời)
            done.append(raw)

        res = reply_stream(history=[{"role": "user", "content": "Chào em"}], system="", llm=FakeLLM(), tts=None,
                           speak=False, turn_log=TurnLog(tmp_path / "turns.jsonl"), kind="chat",
                           after_text=after_text)
        body = res.body_iterator
        async for line in body:
            if line.startswith("data: ") and json.loads(line[6:])["type"] == "text_done":
                break
        await asyncio.sleep(0)  # để produce chạy tới chỗ chờ việc ghi nhớ
        await body.aclose()  # anh ngắt lời: trình duyệt đóng kết nối
        gc.collect()
        gate.set()
        for _ in range(20):
            await asyncio.sleep(0)

    asyncio.run(run())
    assert done == ["[happy] Dạ anh!"]


class OrphanLLM:
    """Model chờ một future mà chỉ chính task tóm tắt giữ (như chờ mạng): nếu task không được ai giữ thì GC dọn cả hai."""

    provider, model = "fake", "fake-model"

    def __init__(self):
        self.ref = None

    async def complete(self, messages, *, json_mode=False, max_tokens=256):
        fut = asyncio.get_running_loop().create_future()
        self.ref = weakref.ref(fut)
        return await fut


def test_tom_tat_nen_khong_bi_don_rac_giua_chung(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.json")
    now = datetime(2026, 11, 14, 21, 0)
    store.record("user", "Hôm nay anh mệt quá, sếp bắt làm thêm giờ cả tuần nay.", now)
    store.record("assistant", "Thương anh ghê.", now)
    llm = OrphanLLM()
    summary = '{"tom_tat": "Anh kể bị làm thêm giờ cả tuần."}'

    async def run():
        # /api/chat bỏ qua giá trị trả về: event loop chỉ giữ task bằng tham chiếu yếu
        schedule_episode_close(store, llm, TurnLog(tmp_path / "turns.jsonl"))
        for _ in range(3):
            await asyncio.sleep(0)
        gc.collect()
        fut = llm.ref()
        assert fut is not None, "task tóm tắt đã bị GC dọn giữa chừng"
        fut.set_result(summary)
        for _ in range(20):
            await asyncio.sleep(0)

    asyncio.run(run())
    assert [e.summary for e in store.list()] == ["Anh kể bị làm thêm giờ cả tuần."]
