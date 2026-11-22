"""Test bộ tách thẻ <ja> khỏi luồng text."""

from app.ja_tags import JaTagParser, strip_ja

SAMPLE = "[happy] Anh về rồi hả! <ja>おかえり！</ja> Kể em nghe đi. <ja>聞かせて。</ja>"


def run(chunks: list[str]) -> tuple[str, list[str]]:
    parser = JaTagParser()
    display, ja = "", []
    for chunk in [*chunks, None]:
        out = parser.flush() if chunk is None else parser.push(chunk)
        display += out.display
        ja += out.ja
    return display, ja


def test_tach_cau_viet_va_nhat():
    assert run([SAMPLE]) == ("[happy] Anh về rồi hả! Kể em nghe đi.", ["おかえり！", "聞かせて。"])


def test_the_bi_cat_moi_vi_tri():
    expected = run([SAMPLE])
    for i in range(len(SAMPLE) + 1):
        assert run([SAMPLE[:i], SAMPLE[i:]]) == expected, i


def test_thieu_the_dong_luc_ket_thuc():
    assert run(["Chào anh. <ja>おかえ"]) == ("Chào anh.", ["おかえ"])


def test_chu_nhat_ngoai_the_bi_an():
    assert run(["Chào anh (おかえり) nha."]) == ("Chào anh nha.", [])


def test_the_viet_sai_kieu():
    assert run(["Dạ! <JA>はい！</JA> Vâng. <jp>ええ。</jp>"]) == ("Dạ! Vâng.", ["はい！", "ええ。"])


def test_strip_ja():
    assert strip_ja("[happy] Dạ! <ja>はい！</ja> Vâng.") == "[happy] Dạ! Vâng."
    assert strip_ja("Chào anh nha.") == "Chào anh nha."


def test_ngoac_trong_khi_bi_cat_moi_vi_tri():
    for text in ["Chào anh (おかえり) nha.", "Dạ (<ja>はい</ja>) nha"]:
        expected = run([text])
        assert expected[0] in ("Chào anh nha.", "Dạ nha"), expected
        for i in range(len(text) + 1):
            assert run([text[:i], text[i:]]) == expected, (text, i)


def test_ngoac_that_van_giu():
    assert run(["Anh (", "ơi) nha ("]) == ("Anh (ơi) nha (", [])


def test_the_lac_cho_khong_lo_ra():
    assert run(["Dạ </ja> nha"]) == ("Dạ nha", [])
    assert run(["Dạ <ja"]) == ("Dạ", [])
    assert run(["Dạ <", "/j"]) == ("Dạ", [])
    assert run(["Dạ <ja>はい</JA> nha </jp>"]) == ("Dạ nha", ["はい"])


def test_quen_the_dong_khong_nuot_chu_viet():
    # Review cuối nhánh: model quên </ja> rồi mở <ja> mới -> chữ Việt ở giữa phải về màn hình, không bị đọc
    assert run(["A! <ja>おかえり！ Hôm nay em vui. <ja>聞かせて。</ja>"]) == (
        "A! Hôm nay em vui.", ["おかえり！", "聞かせて。"])


def test_tag_cam_xuc_trong_the_ja_khong_bi_doc():
    assert run(["Dạ! <ja>[happy]はい！</ja>"]) == ("Dạ!", ["はい！"])


def test_the_ja_khong_co_chu_nhat_thi_khong_doc():
    assert run(["Dạ anh! <ja>Dạ anh</ja>"]) == ("Dạ anh!", [])


def test_chu_latin_trong_cau_nhat_khong_bi_tach_ra():
    # "OK" sau "。" vẫn là câu Nhật: chỉ tách khi phần sau không còn kana/kanji
    assert run(["Được! <ja>はい。OKです！</ja> Đi thôi."]) == ("Được! Đi thôi.", ["はい。OKです！"])
