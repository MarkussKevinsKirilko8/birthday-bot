from app.sources.google_sheets import GoogleSheetsSource
from app.sources.base import get_source
from app.sources.local_file import LocalFileSource


class _FakeWorksheet:
    def get_all_records(self):
        return [
            {"Имя": "Тест", "Отдел": "IT", "Руководитель": "Энди", "Пол": "Male",
             "День рождения": "01.01", "Страна": "Латвия",
             "ID чата отдела": "111", "Доп группы": "222"},
            {"Имя": "", "Отдел": "", "Руководитель": "", "Пол": "",
             "День рождения": "", "Страна": "", "ID чата отдела": "", "Доп группы": ""},
        ]


def test_google_sheets_maps_records():
    src = GoogleSheetsSource(worksheet=_FakeWorksheet())
    rows = src.load()
    assert len(rows) == 1
    assert rows[0].name == "Тест" and rows[0].dept_chat_id == "111"


class _S:
    data_source = "local"
    data_file = "dzimsanas dienas - TEST (bez ID).xlsx"
    gsheet_tab = "Sheet1"


def test_get_source_local():
    assert isinstance(get_source(_S()), LocalFileSource)
