import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("MANAGEMENT_CHAT_ID", "999")
    monkeypatch.setenv("ADMIN_CHAT_ID", "500")
    monkeypatch.setenv("DATA_SOURCE", "local")
    monkeypatch.setenv("DATA_FILE", "dzimsanas dienas - TEST (bez ID).xlsx")
    monkeypatch.setenv("STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setenv("RUN_ON_START", "false")

    import importlib
    import app.config.settings as settings_mod
    importlib.reload(settings_mod)
    settings_mod.get_settings.cache_clear()

    import app.main as main_mod
    importlib.reload(main_mod)

    # stop the scheduler loop from doing anything during tests
    main_mod.SCHEDULER_ENABLED = False

    # replace the bot with a fake that records sends
    sent = []

    class _FakeBot:
        async def send_message(self, chat_id, text):
            sent.append((chat_id, text))

        async def get_me(self):
            class M:
                username = "birthdays_sport_bot"
            return M()

    main_mod.make_bot = lambda token: _FakeBot()
    main_mod._sent = sent

    with TestClient(main_mod.app) as c:
        yield c, main_mod


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_run_endpoint_triggers_send(client):
    c, main_mod = client
    r = c.post("/run")
    assert r.status_code == 200
    # at least the admin summary was sent
    assert any(cid == 500 for cid, _ in main_mod._sent)
