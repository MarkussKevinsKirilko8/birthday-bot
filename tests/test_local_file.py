from app.sources.local_file import LocalFileSource

TEST_XLSX = "dzimsanas dienas - TEST (bez ID).xlsx"


def test_local_file_loads_employees():
    rows = LocalFileSource(TEST_XLSX).load()
    assert len(rows) >= 100                      # ~136 employees
    timon = next(e for e in rows if e.name == "Тимон")
    assert timon.gender == "Male"
    assert timon.department == "Продажи Рагнар"
    assert str(timon.birthday) in ("26.01", "26.1")  # text DD.MM


def test_local_file_skips_blank_name_rows():
    rows = LocalFileSource(TEST_XLSX).load()
    assert all(e.name for e in rows)
