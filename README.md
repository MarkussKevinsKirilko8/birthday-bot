# Birthday & Holiday Notification Bot

Daily Telegram reminders for staff birthdays and RU/LV/BY holidays.
Python + FastAPI + aiogram, runs in Docker. Replaces the old n8n workflow.

## Quick start (testing, local xlsx)

1. `cp .env.example .env` and fill `TELEGRAM_BOT_TOKEN`. For testing, set
   `MANAGEMENT_CHAT_ID` and `ADMIN_CHAT_ID` to your own Telegram ID.
2. Put the test spreadsheet at `data/employees.xlsx`:
   ```bash
   mkdir -p data
   cp "dzimsanas dienas - TEST (bez ID).xlsx" data/employees.xlsx
   ```
   (This test file has every chat ID set to `6091784070`.)
3. Build & run:
   ```bash
   docker compose up -d --build
   ```
4. Trigger a real send to yourself immediately (instead of waiting for 09:00):
   ```bash
   curl -X POST http://localhost:8002/run
   ```
   You'll get the notifications + an admin summary. (Standing in for dept +
   extra + management chats means ~3 copies per event — expected.)
5. Health check: `curl http://localhost:8002/health`
6. Logs: `docker compose logs -f`

## Telegram prerequisites

- Every user must have pressed **Start** on `@birthdays_sport_bot` once.
- The bot must be a **member** of every group whose chat ID appears in the sheet.
  Delivery failures are reported to `ADMIN_CHAT_ID`.

## Cutover to production (Google Sheets)

1. Create a Google service account; share the sheet with its email (read-only).
2. Put the credentials JSON on the server (e.g. `data/gcreds.json`).
3. In `.env`: set `DATA_SOURCE=gsheets`, `GOOGLE_CREDENTIALS_JSON=/data/gcreds.json`,
   `GSHEET_ID=<id>`, `GSHEET_TAB=Sheet1`, and the real `MANAGEMENT_CHAT_ID` /
   `ADMIN_CHAT_ID`.
4. Ensure the "День рождения" column is plain **text** `DD.MM` in the sheet.
5. `docker compose up -d --build`

## Updating the holiday list

Edit `app/holidays.py`. Easter-based dates (Good Friday, Easter, Easter Monday,
Радуница) are year-specific — update them annually (currently set for 2026).

## Tests

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
pytest -q
```
