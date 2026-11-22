"""Log từng lượt không được phình mãi."""

from app.turn_log import TurnLog


def test_log_qua_lon_thi_doi_sang_file_cu(tmp_path):
    path = tmp_path / "turns.jsonl"
    log = TurnLog(path, max_bytes=100)
    for _ in range(5):
        log.write({"kind": "chat", "ms": 1234})
    old = tmp_path / "turns.1.jsonl"
    assert old.exists() and path.exists()
    assert path.stat().st_size <= 100
    total = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in (path, old))
    assert 0 < total <= 5  # chỉ giữ một file cũ: dòng quá cũ bị bỏ
