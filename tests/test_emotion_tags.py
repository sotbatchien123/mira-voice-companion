from app.emotion_tags import EmotionTagParser, parse_complete


def run_stream(chunks: list[str]) -> tuple[str, list[str]]:
    parser = EmotionTagParser()
    text, emotions = "", []
    for c in chunks:
        r = parser.push(c)
        text += r.text
        emotions += r.emotions
    r = parser.flush()
    return text + r.text, emotions + r.emotions


def test_tach_tag_va_map_alias():
    r = parse_complete("[blush] Chào anh~ [sad]")
    assert (r.text, r.emotions) == ("Chào anh~ ", ["happy", "sad"])


def test_bo_tag_la_khong_doi_cam_xuc():
    # tag model tự chế không được lộ ra khung chat hay bị TTS đọc
    r = parse_complete("mảng [foo] nè")
    assert (r.text, r.emotions) == ("mảng nè", [])


def test_tag_tu_che_hay_gap_map_dung_cam_xuc():
    # [concerned] gặp khi chạy thật với qwen3:8b
    r = parse_complete("Anh buồn thật à? [concerned] Sếp mắng vì chuyện gì vậy?")
    assert (r.text, r.emotions) == ("Anh buồn thật à? Sếp mắng vì chuyện gì vậy?", ["sad"])


def test_ghep_tag_bi_cat_giua_cac_chunk():
    assert run_stream(["Hi ", "[hap", "py] ", "anh"]) == ("Hi anh", ["happy"])


def test_khong_de_thua_dau_cach_khi_bo_tag():
    # dấu cách sau tag nằm ở mảnh kế tiếp, kể cả khi giữa chừng có mảnh rỗng
    assert run_stream(["Ủa", "? [sad]", "", " Nhớ"]) == ("Ủa? Nhớ", ["sad"])
    assert run_stream(["[happy]", " Chào", " anh"]) == ("Chào anh", ["happy"])
    # tag lạ cũng bị bỏ, và không để lại dấu cách thừa
    assert run_stream(["a [foo]", " b"]) == ("a b", [])


def test_khong_nuot_dau_ngoac_le_khi_ket_thuc():
    assert run_stream(["giá [", "chưa đóng"]) == ("giá [chưa đóng", [])


def test_dau_ngoac_qua_xa_thi_xa_luon():
    long = "[" + "x" * 40
    assert EmotionTagParser().push(long).text == long
