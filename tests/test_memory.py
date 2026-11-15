"""Test trí nhớ dài hạn (spec 004) bằng LLM giả: không cần Ollama."""

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import ChatTurn, app, get_llm, get_memory, trim_history
from app.memory import (
    MAX_FACTS,
    MemoryStore,
    extract_messages,
    parse_facts,
    remember,
    render_memory,
    system_prompt,
)

NOW = datetime(2026, 11, 14, 21, 30)  # thứ Bảy


class FakeLLM:
    provider, model = "fake", "fake-model"

    def __init__(self, reply="[happy] Dạ em nhớ rồi.", extracted='{"facts": []}', fail=None):
        self.reply, self.extracted, self.fail = reply, extracted, fail
        self.system = None
        self.extract_calls = []

    async def stream(self, history, system=None):
        self.system = system
        yield ("text", self.reply)
        yield ("stop", "end_turn")

    async def complete(self, messages, *, json_mode=False, max_tokens=256):
        if self.fail:
            raise self.fail
        self.extract_calls.append((messages, json_mode))
        return self.extracted

    async def check(self):
        return None


def chat(llm, store, text="Anh tên là Khoa, anh nuôi mèo tên Mướp."):
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_memory] = lambda: store
    body = TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": text}]}).text
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


@pytest.fixture
def store(tmp_path):
    return MemoryStore(tmp_path / "memory.json")


# ---------- kho trí nhớ: luật do code quyết định ----------

def test_loai_mot_gia_tri_thi_thay_dieu_cu(store):
    store.add([("noi_o", "Anh ở Đà Nẵng"), ("thu_cung", "Anh nuôi mèo tên Mướp")], "2026-11-01")
    result = store.add([("noi_o", "Anh chuyển vào Sài Gòn sống")], "2026-11-14")
    assert result == {"added": 1, "replaced": 1}
    assert [(f.kind, f.text) for f in store.facts()] == [("thu_cung", "Anh nuôi mèo tên Mướp"), ("noi_o", "Anh chuyển vào Sài Gòn sống")]


def test_loai_nhieu_gia_tri_thi_cong_don_va_bo_trung(store):
    store.add([("so_thich", "Anh thích anime"), ("so_thich", "Anh thích mèo")], "2026-11-14")
    result = store.add([("so_thich", "anh thích ANIME!")], "2026-11-14")  # trùng (khác hoa thường, dấu câu)
    assert result == {"added": 0, "replaced": 0} and len(store.facts()) == 2


def test_gioi_han_so_dieu_nho_giu_dieu_co_ban(store):
    store.add([("ten", "Anh tên là Khoa")], "2026-11-01")
    store.add([("su_kien", f"Anh kể chuyện số {i}") for i in range(MAX_FACTS + 5)], "2026-11-14")
    facts = store.facts()
    assert len(facts) == MAX_FACTS and facts[0].text == "Anh tên là Khoa"  # tên không bị đẩy ra
    assert "Anh kể chuyện số 0" not in [f.text for f in facts]  # điều cũ nhất bị bỏ


def test_luu_xuong_dia_va_doc_lai(tmp_path):
    path = tmp_path / "memory.json"
    MemoryStore(path).add([("ten", "Anh tên là Khoa")], "2026-11-14")
    fact = MemoryStore(path).facts()[0]
    assert (fact.kind, fact.text, fact.said_on) == ("ten", "Anh tên là Khoa", "2026-11-14")
    assert MemoryStore(path).delete(fact.id) and MemoryStore(path).facts() == []


def test_file_hong_thi_bat_dau_rong(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{hỏng", encoding="utf-8")
    assert MemoryStore(path).facts() == []


# ---------- đọc kết quả của model ----------

def test_doc_json_cua_model_an_toan():
    raw = '{"facts": [{"loai": "ten", "noi_dung": "Anh  tên là Khoa"}, {"loai": "la_lam", "noi_dung": "Anh có xe đạp"},' \
          ' {"loai": "ten", "noi_dung": ""}, "chuỗi lạ", {"noi_dung": "ok"}]}'
    assert parse_facts(raw) == [("ten", "Anh tên là Khoa"), ("khac", "Anh có xe đạp")]
    assert parse_facts("không phải json") == [] and parse_facts('["a"]') == [] and parse_facts('{"facts": "x"}') == []


def test_prompt_trich_xuat_kem_dieu_da_biet(store):
    store.add([("ten", "Anh tên là Khoa")], "2026-11-14")
    content = extract_messages("Anh nuôi mèo", store.facts())[0]["content"]
    assert "- [ten] Anh tên là Khoa" in content and "Anh nuôi mèo" in content
    assert "không tự đổi sang ngày" in content  # spike: model tính ngày sai -> không nhờ nó tính


# ---------- system prompt ----------

def test_system_prompt_co_ngay_gio_va_dieu_da_nho(store):
    store.add([("ten", "Anh tên là Khoa"), ("su_kien", "Anh đi phỏng vấn FPT thứ Bảy tuần sau")], "2026-11-14")
    prompt = system_prompt(NOW, store.facts())
    assert "21:30 (buổi tối), thứ Bảy ngày 14/11/2026" in prompt
    assert "- Anh tên là Khoa (anh nói hôm nay, 14/11/2026)" in prompt
    # mốc tương đối được đổi thành ngày cụ thể (14/11 là thứ Bảy -> thứ Bảy tuần sau là 21/11)
    assert "Anh đi phỏng vấn FPT thứ Bảy ngày 21/11/2026 (sắp tới) (anh nói hôm nay, 14/11/2026)" in prompt


def test_ghi_ro_buoi_va_da_bao_lau():
    from app.memory import Fact, part_of_day

    assert [part_of_day(datetime(2026, 11, 14, h)) for h in (7, 11, 15, 20, 1)] == [
        "buổi sáng", "buổi trưa", "buổi chiều", "buổi tối", "đêm khuya"]
    facts = [Fact("1", "su_kien", "Anh đi phỏng vấn FPT thứ Bảy tuần sau", "2026-11-07"),
             Fact("2", "so_thich", "Anh thích phở", "2026-11-13")]
    text = render_memory(facts, today=NOW)
    assert "(anh nói 7 ngày trước, ngày 07/11/2026)" in text and "(anh nói hôm qua, 13/11/2026)" in text


def test_khong_co_tri_nho_thi_khong_them_muc_tri_nho():
    assert "Những điều em đã biết" not in system_prompt(NOW, [])


def test_tri_nho_cat_theo_gioi_han_ky_tu_uu_tien_dieu_co_ban(store):
    store.add([("ten", "Anh tên là Khoa")], "2026-11-01")
    store.add([("su_kien", f"Anh kể một chuyện khá dài số {i}") for i in range(40)], "2026-11-14")
    text = render_memory(store.facts(), limit=200)
    assert len(text) <= 200 and text.startswith("- Anh tên là Khoa")
    assert "số 39" in text  # sau điều cơ bản là điều mới nhất


# ---------- cắt lịch sử theo ngân sách ----------

def test_cat_lich_su_theo_so_ky_tu():
    turns = [ChatTurn(role=r, content=("x" * 900)) for r in ["user", "assistant"] * 6] + [ChatTurn(role="user", content="cuối")]
    kept = trim_history(turns, char_budget=3000)
    assert sum(len(t["content"]) for t in kept) <= 3000
    assert kept[0]["role"] == "user" and kept[-1]["content"] == "cuối"


def test_tin_cuoi_luon_duoc_giu_du_dai_hon_ngan_sach():
    kept = trim_history([ChatTurn(role="user", content="y" * 4000)], char_budget=100)
    assert len(kept) == 1


# ---------- qua API ----------

def test_luot_chat_dung_system_prompt_va_ghi_nho(store):
    llm = FakeLLM(extracted='{"facts": [{"loai": "ten", "noi_dung": "Anh tên là Khoa"}, '
                            '{"loai": "thu_cung", "noi_dung": "Anh nuôi mèo tên Mướp"}]}')
    events = chat(llm, store)
    assert events[-1]["type"] == "done"
    assert "Bây giờ là" in llm.system  # có ngày giờ
    assert llm.extract_calls and llm.extract_calls[0][1] is True  # gọi trích xuất ở chế độ JSON
    assert [f.text for f in store.facts()] == ["Anh tên là Khoa", "Anh nuôi mèo tên Mướp"]
    # lượt sau: điều đã nhớ có trong system prompt
    llm2 = FakeLLM()
    chat(llm2, store, "Em còn nhớ mèo của anh tên gì không?")
    assert "Anh nuôi mèo tên Mướp" in llm2.system


def test_tin_qua_ngan_khong_ton_luot_trich_xuat(store):
    llm = FakeLLM()
    chat(llm, store, "ok")
    assert llm.extract_calls == []


def test_loi_trich_xuat_khong_lam_hong_chat(store, offline_voice_and_log):
    events = chat(FakeLLM(fail=RuntimeError("Ollama sập")), store)
    assert events[-1]["type"] == "done" and store.facts() == []
    records = [json.loads(line) for line in offline_voice_and_log.read_text(encoding="utf-8").splitlines()]
    mem = [r for r in records if r.get("kind") == "memory"][0]
    assert mem["error"] == "RuntimeError" and "Khoa" not in json.dumps(records, ensure_ascii=False)


def test_api_xem_va_quen(store):
    store.add([("ten", "Anh tên là Khoa"), ("thu_cung", "Anh nuôi mèo tên Mướp")], "2026-11-14")
    app.dependency_overrides[get_memory] = lambda: store
    client = TestClient(app)
    facts = client.get("/api/memory").json()["facts"]
    assert [f["text"] for f in facts] == ["Anh tên là Khoa", "Anh nuôi mèo tên Mướp"]
    assert client.delete(f"/api/memory/{facts[0]['id']}").json() == {"ok": True}
    assert client.delete("/api/memory/khong-co").status_code == 404
    assert [f["text"] for f in client.get("/api/memory").json()["facts"]] == ["Anh nuôi mèo tên Mướp"]
    client.delete("/api/memory")
    assert client.get("/api/memory").json() == {"enabled": True, "facts": [], "episodes": []}


def test_tat_tri_nho():
    app.dependency_overrides[get_memory] = lambda: None
    assert TestClient(app).get("/api/memory").json() == {"enabled": False, "facts": [], "episodes": []}


async def _remember_skips_short(store):
    return await remember(FakeLLM(), store, "hi", NOW)


def test_remember_bo_qua_tin_ngan(store):
    import asyncio

    assert asyncio.run(_remember_skips_short(store))["skipped"] is True


def test_doi_moc_thoi_gian_tuong_doi_thanh_ngay():
    from app.memory import resolve_relative_dates

    # nói ngày thứ Bảy 07/11/2026
    assert resolve_relative_dates("Anh đi phỏng vấn ở FPT vào thứ Bảy tuần sau", "2026-11-07") ==         "Anh đi phỏng vấn ở FPT vào thứ Bảy ngày 14/11/2026"
    assert resolve_relative_dates("Anh sắp đi phỏng vấn vào ngày mai", "2026-11-12") == "Anh sắp đi phỏng vấn vào ngày 13/11/2026"
    assert resolve_relative_dates("Hôm qua anh bị ốm", "2026-11-12") == "ngày 11/11/2026 anh bị ốm"
    assert resolve_relative_dates("Chủ nhật này anh về quê", "2026-11-12") == "Chủ nhật ngày 15/11/2026 anh về quê"
    assert resolve_relative_dates("Tuần sau anh thi", "2026-11-12") == "tuần bắt đầu ngày 16/11/2026 anh thi"
    assert resolve_relative_dates("Anh thích mèo", "2026-11-12") == "Anh thích mèo"  # không có mốc thời gian


def test_thu_x_nay_da_qua_trong_tuan_thi_la_tuan_toi():
    from app.memory import resolve_relative_dates

    # 15/11/2026 là Chủ nhật: "thứ Bảy này" là thứ Bảy sắp tới (21/11), không phải hôm qua (14/11)
    assert resolve_relative_dates("Thứ Bảy này anh đi phỏng vấn", "2026-11-15") == "Thứ Bảy ngày 21/11/2026 anh đi phỏng vấn"
    # 11/11/2026 là thứ Tư: thứ Hai đã qua -> tuần tới; thứ Tư là chính hôm nay
    assert resolve_relative_dates("thứ Hai này anh thi", "2026-11-11") == "thứ Hai ngày 16/11/2026 anh thi"
    assert resolve_relative_dates("thứ Tư này anh bận", "2026-11-11") == "thứ Tư ngày 11/11/2026 anh bận"


def test_quen_het_luc_dang_trich_xuat_khong_them_lai(store):
    """Bấm "Quên hết" trong lúc model đang trích điều đáng nhớ: điều vừa trích không được thêm lại."""
    import asyncio

    class SlowLLM(FakeLLM):
        def __init__(self, gate):
            super().__init__(extracted='{"facts": [{"loai": "ten", "noi_dung": "Anh tên là Khoa"}]}')
            self.gate = gate

        async def complete(self, messages, *, json_mode=False, max_tokens=256):
            await self.gate.wait()
            return await super().complete(messages, json_mode=json_mode, max_tokens=max_tokens)

    async def run():
        gate = asyncio.Event()
        task = asyncio.create_task(remember(SlowLLM(gate), store, "Anh tên là Khoa, anh làm kỹ sư", NOW))
        await asyncio.sleep(0)
        store.clear()
        gate.set()
        return await task

    assert asyncio.run(run())["added"] == 0
    assert store.facts() == []


def test_prompt_dung_ngay_cu_the_cho_su_kien():
    from app.memory import Fact

    facts = [Fact("1", "su_kien", "Anh sắp đi phỏng vấn ở FPT vào ngày mai", "2026-11-12")]
    assert ("Anh sắp đi phỏng vấn ở FPT vào ngày 13/11/2026 (đã diễn ra) (anh nói 2 ngày trước, ngày 12/11/2026)"
            in system_prompt(NOW, facts))


def test_nhan_da_dien_ra_hom_nay_sap_toi():
    from app.memory import event_status

    assert event_status("Anh thi vào ngày 13/11/2026", NOW) == " (đã diễn ra)"
    assert event_status("Anh thi vào ngày 14/11/2026", NOW) == " (là hôm nay)"
    assert event_status("Anh thi vào ngày 20/11/2026", NOW) == " (sắp tới)"
    assert event_status("Anh thích mèo", NOW) == ""
