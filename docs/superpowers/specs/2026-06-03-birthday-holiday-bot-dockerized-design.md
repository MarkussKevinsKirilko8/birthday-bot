# Birthday & Holiday Notification Bot — Dockerized (Python) Design

**Date:** 2026-06-03
**Status:** Approved (pending spec review)
**Owner:** info@abcd.lv

## 1. Purpose

Replace the existing n8n workflow (Schedule → Google Sheets → Code → IF → HTTP Request)
with a standalone, self-contained Python service that runs in Docker on the existing
DigitalOcean Droplet, alongside the other Telegram bots (e.g. *AI Sales Agent Claude*).

The bot sends Telegram reminders for:
- **Birthdays** — at 7, 2, and 0 days before, routed per department + extra groups + management.
- **Holidays** — RU + Latvia + Belarus set (v4 holiday list, including the newly added
  Latvian holidays), gendered (23 Feb / 8 Mar) and general, with custom per-day messages.

Behaviour, message text, emojis, and routing must match the current n8n `birthday-code.js`
(v4) **exactly**. This is a re-platforming, not a redesign of the notifications.

## 2. Scope

**In scope**
- Daily scheduled run at 09:00 Asia/Tbilisi.
- Two swappable data sources: local `.xlsx` (testing) and Google Sheets (production).
- Sending via the `@birthdays_sport_bot` token through the Telegram Bot API (aiogram).
- Error logging + admin-chat summary/alerts.
- Docker + docker-compose deployment matching the fleet's conventions.

**Out of scope (explicitly deferred)**
- Holidays for countries other than RU/LV/BY (Kazakhstan, Ukraine, Georgia, Poland, Spain).
  Noted as a future option; the data contains staff from these countries but the holiday
  list intentionally does not cover them yet.
- Per-country routing of holidays (current behaviour blasts each holiday to all chats).
- Any web UI, dashboards, or database-backed state.

## 3. Stack

Mirrors the *AI Sales Agent Claude* project's idiom, **right-sized** (no Postgres, no Redis —
this is a daily batch job, not a stateful conversational service).

- **Python 3.12-slim** (same Dockerfile base/shape; `uvicorn app.main:app`).
- **aiogram 3.x** — Telegram message sending.
- **pydantic-settings + `.env`** — config (committed `.env.example`).
- **FastAPI** — slim app exposing `GET /health` and `POST /run` (manual trigger),
  matching the agent's `/scrape` manual-trigger pattern.
- **asyncio scheduler loop** inside FastAPI `lifespan` — sleeps until the next 09:00 in the
  configured timezone, then runs.
- **openpyxl** — read local `.xlsx`.
- **gspread** (+ google-auth) — read Google Sheets (built now, activated later).
- **docker-compose** — single service, `env_file: .env`, `restart: unless-stopped`,
  host port `8002:8000`, data file + state on a mounted volume.

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Docker container (Python, always running)                    │
│                                                                │
│  FastAPI (app.main)                                            │
│    ├─ GET  /health         → liveness                          │
│    ├─ POST /run            → manual trigger (testing)          │
│    └─ lifespan ─ asyncio scheduler loop                        │
│            every day at RUN_TIME (TZ-aware) → run_daily()      │
│                                                                │
│  run_daily():                                                  │
│    1. source.load()      ── swappable ──┐                      │
│         • LocalFileSource (xlsx)  [test]│                      │
│         • GoogleSheetsSource      [prod]│                      │
│    2. build_messages(rows, today)  → [(chat_id, text), …]      │
│         (logic ported from birthday-code.js v4, identical)     │
│    3. telegram.send_all()  → per-message try/except + delay    │
│    4. report summary/errors → ADMIN_CHAT                       │
│    5. write last-run date → /data/state.json (dedupe)          │
└─────────────────────────────────────────────────────────────┘
        │ data file on mounted volume        │ Telegram Bot API
        ▼                                     ▼
  /data/employees.xlsx                  @birthdays_sport_bot
  (or Google Sheets)                    → dept / extra / mgmt chats
```

## 5. Components

Each module has one purpose, a clear interface, and is independently testable.

| Module | Responsibility | Interface |
|---|---|---|
| `app/main.py` | FastAPI app, `/health`, `/run`, lifespan, scheduler wiring | HTTP + startup |
| `app/config/settings.py` | All config via pydantic-settings; validate on startup | `settings` object |
| `app/sources/base.py` | Data-source contract | `load() -> list[Employee]` |
| `app/sources/local_file.py` | Read `.xlsx` (openpyxl) into `Employee` rows | implements `base` |
| `app/sources/google_sheets.py` | Read live sheet (gspread) into `Employee` rows | implements `base` |
| `app/logic.py` | Port of `birthday-code.js` v4 — birthdays + holidays + routing | `build_messages(rows, today) -> list[Message]` |
| `app/telegram.py` | Send via aiogram, rate-limit, per-message error capture | `send_all(messages) -> SendReport` |
| `app/scheduler.py` | Next-run calc (TZ-aware), dedupe via state file | `next_run_at()`, `should_run_today()` |

### Data model
`Employee` (dataclass / pydantic) with the sheet columns:
`name, department, team_lead, gender, birthday (DD.MM str), country, dept_chat_id, extra_groups`.
`Message = (chat_id: int, text: str)`.

### Source selection
`DATA_SOURCE=local|gsheets` chooses the implementation at startup. Both return the same
`list[Employee]`, so `logic.py` and everything downstream are source-agnostic. Switching to
production = change one env var (plus provide Google credentials).

## 6. Configuration (`.env`)

| Var | Example | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `123:ABC…` | `@birthdays_sport_bot` token |
| `MANAGEMENT_CHAT_ID` | `-100…` | Gets all notifications **with country** |
| `ADMIN_CHAT_ID` | `6091784070` | Receives run summary / error alerts |
| `TIMEZONE` | `Asia/Tbilisi` | Scheduler timezone |
| `RUN_TIME` | `09:00` | Daily run time |
| `DATA_SOURCE` | `local` | `local` or `gsheets` |
| `DATA_FILE` | `/data/employees.xlsx` | Used when `DATA_SOURCE=local` |
| `RUN_ON_START` | `false` | If `true`, run once immediately on boot (testing) |
| `GOOGLE_CREDENTIALS_JSON` | `/data/gcreds.json` | Used when `DATA_SOURCE=gsheets` |
| `GSHEET_ID` | `1AbC…` | Spreadsheet ID (production) |
| `GSHEET_TAB` | `Sheet1` | Worksheet/tab name |

`MANAGEMENT_CHAT` is no longer hardcoded in source (the n8n version had a `'. . . .'`
placeholder that crashed the node) — it moves to `MANAGEMENT_CHAT_ID`.

## 7. Notification logic (the one real risk, mitigated)

`birthday-code.js` v4 is ported to `app/logic.py` with **identical**:
- message strings, emojis, and line structure (short vs. full/management variants),
- birthday reminder days `[7, 2, 0]`,
- holiday list incl. the new Latvian holidays (Страстная пятница 03.04, Второй день Пасхи
  06.04, Сочельник 24.12, Второй день Рождества 26.12, Канун Нового года 31.12),
- gendered vs. general handling and custom `msg21/msg14/msg7/msg2/msgDay` selection,
- routing: dept chat (short) + extra groups (short) + management (full, with country).

Helpers `getDiffDays` / `parseDDMM` / `addResult` become small Python functions.
`build_messages(rows, today)` accepts an injectable `today` (date) so tests assert exact
output for known dates.

**Date parsing note:** the birthday column must be text `DD.MM`. The source xlsx stored
dates as numbers, which dropped trailing zeros (October `14.10 → 14.1`, misread as January).
The test file has been reformatted to text `DD.MM`; `parse_ddmm` also defensively handles a
numeric input by reconstructing the month (`.1 → 10`, `.01 → 1`). Google Sheets should store
this column as plain text.

## 8. Reliability & errors

- **Dedupe:** last successful run date persisted to `/data/state.json` on the volume; a
  container restart on the same day will not re-send.
- **Per-message resilience:** each send is wrapped in try/except; one failure (e.g. a 403
  from a chat the bot isn't in) is logged and skipped — the run continues.
- **Admin reporting:** at end of run, a summary goes to `ADMIN_CHAT`
  (`✅ sent N / ⚠️ M failed (chat ids …)`), or a fatal alert
  (`❌ data source unreachable`). Everything also goes to stdout for `docker logs`.

## 9. Telegram prerequisites (rollout)

A bot can only message a chat it has access to:
- **Users** must have pressed **Start** (`/start`) on `@birthdays_sport_bot` at least once,
  or sends return `403: bot can't initiate conversation with a user`. (Confirmed done for
  the team and the test ID `6091784070`.)
- **Groups**: `@birthdays_sport_bot` must be a member of every department/management group
  whose chat ID appears in the sheet.
Failures here surface in the admin summary rather than failing silently.

## 10. Testing

- **Unit (`tests/test_logic.py`):** feed sample `Employee` rows with a fixed `today`, assert
  the exact `[(chat_id, text)]` list. Cover: a 7-day birthday, a same-day birthday, the
  reformatted October birthdays, a 23 Feb male-only list, an 8 Mar female-only list, a
  general holiday blast, and the new Latvian holidays.
- **Source tests:** `local_file` parses the test xlsx into the expected rows.
- **End-to-end (manual):** `POST /run` (or `RUN_ON_START=true`) with the test file
  `dzimsanas dienas - TEST (bez ID).xlsx` (all chat IDs = `6091784070`) → real send to self.
  Note: standing in for dept + extra + management means ~3 copies per event — expected.

## 11. Deployment

- `Dockerfile` (python:3.12-slim, install `requirements.txt`, `uvicorn app.main:app`).
- `docker-compose.yml`: single `app` service, `env_file: .env`, `restart: unless-stopped`,
  `ports: "8002:8000"`, volume mounting `/data` (data file + state.json).
- `requirements.txt`: fastapi, uvicorn, aiogram, pydantic-settings, openpyxl, gspread,
  google-auth, httpx, tzdata.
- `.env.example` committed; `.env` git-ignored.
- `README.md`: build/run commands and the Google-Sheets cutover steps.

### Cutover to production (Google Sheets)
1. Create a Google service account, share the sheet with its email (read-only).
2. Put the credentials JSON on the server, set `GOOGLE_CREDENTIALS_JSON`, `GSHEET_ID`,
   `GSHEET_TAB`.
3. Set `DATA_SOURCE=gsheets`, set real `MANAGEMENT_CHAT_ID` / `ADMIN_CHAT_ID`, redeploy.

## 12. Open items / future

- Optional later: add KZ/UA/GE/PL/ES national holidays + per-country holiday routing.
- Floating Latvian/Belarusian dates (Easter-based: Good Friday, Easter, Easter Monday,
  Радуница) are year-specific and must be updated annually — currently set for 2026.
