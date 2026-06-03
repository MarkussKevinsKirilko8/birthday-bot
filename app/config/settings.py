from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    management_chat_id: int
    admin_chat_id: int

    # Scheduling
    timezone: str = "Asia/Tbilisi"
    run_time: str = "09:00"
    run_on_start: bool = False

    # Data source
    data_source: str = "local"          # "local" | "gsheets"
    data_file: str = "/data/employees.xlsx"
    state_file: str = "/data/state.json"

    # Google Sheets (used only when data_source == "gsheets")
    google_credentials_json: str = ""
    gsheet_id: str = ""
    gsheet_tab: str = "Sheet1"

    model_config = {"env_file": ".env", "extra": "ignore"}



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
