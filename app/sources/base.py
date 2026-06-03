from __future__ import annotations
from typing import Protocol
from app.models import Employee


class DataSource(Protocol):
    def load(self) -> list[Employee]:
        ...


# Column header -> Employee field
COLUMNS = {
    "Имя": "name",
    "Отдел": "department",
    "Руководитель": "team_lead",
    "Пол": "gender",
    "День рождения": "birthday",
    "Страна": "country",
    "ID чата отдела": "dept_chat_id",
    "Доп группы": "extra_groups",
}


def row_to_employee(record: dict) -> Employee | None:
    def g(header):
        v = record.get(header, "")
        return "" if v is None else (v if header == "День рождения" else str(v).strip())
    name = g("Имя")
    if not name:
        return None
    return Employee(
        name=name,
        department=g("Отдел"),
        team_lead=g("Руководитель"),
        gender=g("Пол"),
        birthday=record.get("День рождения") or "",
        country=g("Страна"),
        dept_chat_id=g("ID чата отдела"),
        extra_groups=g("Доп группы"),
    )


def get_source(settings) -> DataSource:
    if settings.data_source == "gsheets":
        from app.sources.google_sheets import GoogleSheetsSource
        return GoogleSheetsSource(
            credentials_json=settings.google_credentials_json,
            sheet_id=settings.gsheet_id,
            tab=settings.gsheet_tab,
        )
    from app.sources.local_file import LocalFileSource
    return LocalFileSource(settings.data_file, sheet=settings.gsheet_tab)
