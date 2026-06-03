import pytest
from app.config.settings import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("MANAGEMENT_CHAT_ID", "555")
    monkeypatch.setenv("ADMIN_CHAT_ID", "6091784070")
    s = Settings(_env_file=None)
    assert s.telegram_bot_token == "tok"
    assert s.management_chat_id == 555
    assert s.admin_chat_id == 6091784070
    # defaults
    assert s.timezone == "Asia/Tbilisi"
    assert s.run_time == "09:00"
    assert s.data_source == "local"
    assert s.run_on_start is False


def test_settings_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(Exception):
        Settings(_env_file=None)
