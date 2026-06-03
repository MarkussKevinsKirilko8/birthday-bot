from __future__ import annotations
from app.models import Employee
from app.sources.base import row_to_employee


class GoogleSheetsSource:
    """Reads a worksheet's records into Employee rows. The worksheet can be
    injected (tests) or built from credentials at runtime."""

    def __init__(self, worksheet=None, credentials_json: str = "",
                 sheet_id: str = "", tab: str = "Sheet1"):
        self._worksheet = worksheet
        self.credentials_json = credentials_json
        self.sheet_id = sheet_id
        self.tab = tab

    def _open(self):
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(self.credentials_json, scopes=scopes)
        gc = gspread.authorize(creds)
        return gc.open_by_key(self.sheet_id).worksheet(self.tab)

    def load(self) -> list[Employee]:
        ws = self._worksheet or self._open()
        out: list[Employee] = []
        for record in ws.get_all_records():
            emp = row_to_employee(record)
            if emp:
                out.append(emp)
        return out
