# Birthday & Holiday Notification Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-platform the n8n birthday/holiday reminder workflow into a standalone Python service that runs in Docker on the existing DigitalOcean Droplet, sending Telegram messages via `@birthdays_sport_bot` on a daily 09:00 schedule.

**Architecture:** A slim FastAPI app whose `lifespan` starts an asyncio loop that fires once per day at `RUN_TIME` (TZ-aware). Each run loads employees from a swappable data source (local `.xlsx` for testing, Google Sheets for production), builds the exact same messages as the n8n `birthday-code.js` v4, sends them via aiogram with per-message error capture, and reports a summary to an admin chat. No Postgres/Redis — this is a daily batch job. Matches the fleet's `pydantic-settings` + `.env` + docker-compose conventions.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, aiogram 3.x, pydantic-settings, openpyxl, gspread + google-auth, pytest.

---

## File Structure

```
birthday-bot/
  app/
    __init__.py
    main.py              # FastAPI + lifespan + daily scheduler loop + /health, /run
    runner.py            # run_daily(): load -> build -> send -> report -> mark state
    logic.py             # port of birthday-code.js v4 (helpers + build_messages)
    models.py            # Employee, Message dataclasses
    telegram.py          # aiogram send_all() + SendReport
    scheduler.py         # next_run_at(), state-file dedupe
    config/
      __init__.py
      settings.py        # pydantic-settings BaseSettings
    sources/
      __init__.py
      base.py            # DataSource protocol + get_source() factory
      local_file.py      # openpyxl reader  [testing]
      google_sheets.py   # gspread reader   [production]
  tests/
    __init__.py
    conftest.py          # shared fixtures (sample rows, fixed date)
    test_logic.py        # exact-output tests for birthdays + holidays
    test_scheduler.py    # next-run + state dedupe
    test_local_file.py   # xlsx parsing against the committed test file
    test_telegram.py     # send_all with a fake bot
    test_runner.py       # orchestration with fakes
    test_main.py         # /health and /run via TestClient
  data/                  # (gitignored) mounted volume: employees.xlsx + state.json
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
  README.md
```

Each module has one responsibility. `logic.py` is pure (no I/O) so its output can be pinned exactly by tests — this is the guarantee that the JS→Python port preserves message text/routing.

---

## Task 1: Project scaffold + dependencies + pytest

**Files:**
- Create: `requirements.txt`, `app/__init__.py`, `app/config/__init__.py`, `app/sources/__init__.py`, `tests/__init__.py`, `pytest.ini`

- [ ] **Step 1: Create package directories and empty `__init__.py` files**

```bash
mkdir -p app/config app/sources tests data
touch app/__init__.py app/config/__init__.py app/sources/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
fastapi==0.115.6
uvicorn==0.34.0
pydantic-settings==2.7.1
aiogram==3.19.0
openpyxl==3.1.5
gspread==6.1.4
google-auth==2.37.0
httpx==0.28.1
tzdata==2024.2

# dev/test
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 3: Write `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Create and activate a virtualenv, install deps**

Run:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```
Expected: installs succeed, ends with "Successfully installed …".

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `. .venv/bin/activate && pytest -q`
Expected: "no tests ran" (exit code 5) — confirms pytest is wired.

- [ ] **Step 6: Add `.venv/` to `.gitignore` (if not present) and commit**

```bash
grep -qxF '.venv/' .gitignore || echo '.venv/' >> .gitignore
git add requirements.txt pytest.ini app tests .gitignore
git commit -m "chore: scaffold project, deps, pytest"
```

---

## Task 2: Date helpers — `parse_ddmm` and `diff_days`

These are the core date primitives ported from `getDiffDays`/`parseDDMM` in `birthday-code.js`. `diff_days` mimics JS `Date` month overflow (so an invalid day like 31.04 rolls over instead of crashing). `parse_ddmm` accepts a `"DD.MM"` string and also defensively reconstructs a numeric value (Excel stored `14.10` as `14.1`).

**Files:**
- Create: `app/logic.py`
- Test: `tests/test_logic.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logic.py
from datetime import date
from app.logic import parse_ddmm, diff_days


def test_parse_ddmm_string():
    assert parse_ddmm("26.01") == (26, 1)
    assert parse_ddmm("14.10") == (14, 10)
    assert parse_ddmm(" 03.02 ") == (3, 2)


def test_parse_ddmm_numeric_reconstructs_month():
    # Excel dropped the trailing zero: 14.10 -> 14.1 ; .01 -> 1 (Jan)
    assert parse_ddmm(14.1) == (14, 10)
    assert parse_ddmm(26.01) == (26, 1)
    assert parse_ddmm(8.11) == (8, 11)


def test_parse_ddmm_invalid():
    assert parse_ddmm(None) == None
    assert parse_ddmm("") == None
    assert parse_ddmm("nope") == None
    assert parse_ddmm("40.01") == None
    assert parse_ddmm("10.13") == None


def test_diff_days_basic():
    today = date(2026, 6, 3)
    assert diff_days(3, 6, today) == 0
    assert diff_days(10, 6, today) == 7
    assert diff_days(5, 6, today) == 2


def test_diff_days_overflow_does_not_crash():
    # 31.04 is not a real date; JS rolled it to May 1 — we must not raise
    today = date(2026, 4, 28)
    assert diff_days(31, 4, today) == 3  # Apr has 30 days -> May 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_logic.py -q`
Expected: FAIL — `ImportError: cannot import name 'parse_ddmm' from 'app.logic'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/logic.py
from __future__ import annotations
from datetime import date, timedelta


def parse_ddmm(value):
    """Return (day, month) or None. Accepts 'DD.MM' text or a numeric value
    where Excel dropped a trailing zero (14.10 -> 14.1)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        day = int(value)
        month = round((value - day) * 100)
    else:
        s = str(value).strip()
        if "." not in s:
            return None
        parts = s.split(".")
        try:
            day = int(parts[0])
            month = int(parts[1])
        except (ValueError, IndexError):
            return None
    if 1 <= day <= 31 and 1 <= month <= 12:
        return (day, month)
    return None


def diff_days(day: int, month: int, today: date) -> int:
    """Whole days from `today` to day/month of today's year.
    Mimics JS Date overflow: an out-of-range day rolls into the next month."""
    base = date(today.year, month, 1)
    target = base + timedelta(days=day - 1)
    return (target - today).days
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_logic.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/logic.py tests/test_logic.py
git commit -m "feat: date helpers parse_ddmm and diff_days"
```

---

## Task 3: Data model — `Employee` and `Message`

**Files:**
- Create: `app/models.py`
- Test: `tests/test_logic.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_logic.py (append)
from app.models import Employee, Message


def test_employee_extra_group_ids_parsing():
    e = Employee(name="X", department="", team_lead="", gender="Male",
                 birthday="01.01", country="", dept_chat_id="111",
                 extra_groups="222, 333 ,")
    assert e.extra_group_ids() == ["222", "333"]
    assert Employee(name="X", department="", team_lead="", gender="",
                    birthday="", country="", dept_chat_id="",
                    extra_groups="").extra_group_ids() == []


def test_message_holds_int_chat_id():
    m = Message(chat_id=123, text="hi")
    assert m.chat_id == 123 and m.text == "hi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logic.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/models.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Employee:
    name: str
    department: str
    team_lead: str
    gender: str
    birthday: str          # "DD.MM" (may also arrive numeric from xlsx)
    country: str
    dept_chat_id: str      # column G
    extra_groups: str      # column H (comma-separated)

    def extra_group_ids(self) -> list[str]:
        if not self.extra_groups:
            return []
        return [p.strip() for p in str(self.extra_groups).split(",") if p.strip()]


@dataclass(frozen=True)
class Message:
    chat_id: int
    text: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logic.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_logic.py
git commit -m "feat: Employee and Message models"
```

---

## Task 4: Birthday message building

Port of BLOCK 1 of `birthday-code.js`. `build_birthday_messages(rows, today, management_chat_id)` returns a `list[Message]`. Routing: dept chat (short, no country) + each extra group (short) + management (full, with country). Message text must be byte-identical to the JS.

**Files:**
- Modify: `app/logic.py`
- Test: `tests/test_logic.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logic.py (append)
from app.logic import build_birthday_messages

MGMT = 7013407968


def _emp(**kw):
    base = dict(name="Тимон", department="Продажи", team_lead="Рагнар",
                gender="Male", birthday="10.06", country="Казахстан",
                dept_chat_id="111", extra_groups="222")
    base.update(kw)
    return Employee(**base)


def test_birthday_7_days_routing_and_text():
    today = date(2026, 6, 3)  # 7 days before 10.06
    msgs = build_birthday_messages([_emp()], today, MGMT)
    by_chat = {m.chat_id: m.text for m in msgs}
    assert set(by_chat) == {111, 222, MGMT}
    short = ("📅 Через неделю день рождения!\n👤 Тимон\n"
             "🏢 Продажи\n📌 Ответственный: Рагнар\n\nПодготовь поздравление!")
    full = ("📅 Через неделю день рождения!\n👤 Тимон\n"
            "🏢 Продажи\n🌍 Казахстан\n📌 Ответственный: Рагнар\n\nПодготовь поздравление!")
    assert by_chat[111] == short
    assert by_chat[222] == short
    assert by_chat[MGMT] == full


def test_birthday_today_text():
    today = date(2026, 6, 10)
    msgs = build_birthday_messages([_emp(dept_chat_id="", extra_groups="")], today, MGMT)
    assert len(msgs) == 1 and msgs[0].chat_id == MGMT
    assert msgs[0].text.startswith("🎂 Сегодня день рождения!\n👤 Тимон\n")
    assert msgs[0].text.endswith("\nПоздравляй! 🎉")


def test_birthday_no_match_returns_empty():
    today = date(2026, 1, 1)
    assert build_birthday_messages([_emp()], today, MGMT) == []


def test_october_birthday_numeric_is_handled():
    # birthday came in as numeric 14.1 (really 14.10)
    today = date(2026, 10, 7)  # 7 days before 14.10
    msgs = build_birthday_messages([_emp(birthday=14.1, dept_chat_id="", extra_groups="")], today, MGMT)
    assert len(msgs) == 1 and "Через неделю" in msgs[0].text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_logic.py -q`
Expected: FAIL — `cannot import name 'build_birthday_messages'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/logic.py (append)
from app.models import Employee, Message

BIRTHDAY_REMIND_DAYS = [7, 2, 0]


def _add(results, text, chat_id):
    if text and chat_id is not None and str(chat_id).strip() != "":
        results.append(Message(chat_id=int(str(chat_id).strip()), text=text))


def _birthday_text(prefix, footer, name, department, team_lead, country=None):
    msg = f"{prefix}\n👤 {name}\n"
    if department:
        msg += f"🏢 {department}\n"
    if country:
        msg += f"🌍 {country}\n"
    if team_lead:
        msg += f"📌 Ответственный: {team_lead}\n"
    msg += f"\n{footer}"
    return msg


_BDAY_FORMS = {
    7: ("📅 Через неделю день рождения!", "Подготовь поздравление!"),
    2: ("⏰ Послезавтра день рождения!", "Не забудь поздравить!"),
    0: ("🎂 Сегодня день рождения!", "Поздравляй! 🎉"),
}


def build_birthday_messages(rows: list[Employee], today, management_chat_id) -> list[Message]:
    results: list[Message] = []
    for e in rows:
        if not e.name or e.birthday in (None, ""):
            continue
        bd = parse_ddmm(e.birthday)
        if not bd:
            continue
        d = diff_days(bd[0], bd[1], today)
        if d not in BIRTHDAY_REMIND_DAYS:
            continue
        prefix, footer = _BDAY_FORMS[d]
        short = _birthday_text(prefix, footer, e.name, e.department, e.team_lead)
        full = _birthday_text(prefix, footer, e.name, e.department, e.team_lead, e.country)
        if e.dept_chat_id:
            _add(results, short, e.dept_chat_id)
        for extra in e.extra_group_ids():
            _add(results, short, extra)
        _add(results, full, management_chat_id)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_logic.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/logic.py tests/test_logic.py
git commit -m "feat: birthday message building (BLOCK 1 port)"
```

---

## Task 5: Holiday data (v4 list)

Port the v4 `HOLIDAYS` array (incl. the new Latvian holidays) into Python as a module-level list of dicts. Kept in its own task so the data is reviewable in isolation.

**Files:**
- Create: `app/holidays.py`
- Test: `tests/test_logic.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_logic.py (append)
from app.holidays import HOLIDAYS


def test_holiday_list_has_v4_entries():
    dates = {h["date"] for h in HOLIDAYS}
    # newly added Latvian holidays must be present
    assert {"03.04", "06.04", "24.12", "26.12", "31.12"} <= dates
    assert len(HOLIDAYS) == 23
    # every entry has the required keys
    for h in HOLIDAYS:
        assert {"date", "name", "icon", "gender", "remind_days"} <= set(h)
        assert h["gender"] in ("all", "Male", "Female")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logic.py::test_holiday_list_has_v4_entries -q`
Expected: FAIL — `No module named 'app.holidays'`.

- [ ] **Step 3: Write implementation** (transcribe verbatim from `birthday-code.js` v4)

```python
# app/holidays.py
# Ported verbatim from birthday-code.js v4. Floating (Easter-based) dates are
# year-specific (2026) — see the "ОБНОВЛЯТЬ ЕЖЕГОДНО" notes in birthday-code.js.

HOLIDAYS = [
    {"date": "01.01", "name": "Новый год", "icon": "🎄", "gender": "all",
     "remind_days": [21, 14, 7, 0],
     "msg21": "🎄 Через три недели — Новый год!\nСамое время начать думать о подарках и планах! 🎁",
     "msg14": "🎄 Через две недели — Новый год!\nПора начинать подготовку к празднику! 🎁",
     "msg7": "🎄 Через неделю — Новый год!\nФинальная неделя — подарки, поздравления, планы! 🎅",
     "msgDay": "🎄 Хо-хо-хо! С Новым годом! 🎉\nПусть новый год принесёт удачу, новые победы и классную команду!\nС праздником, коллеги! 🥂"},
    {"date": "07.01", "name": "Рождество Христово (РФ, Беларусь)", "icon": "⛪", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "⛪ С Рождеством Христовым!\nСветлого праздника, коллеги! 🙏"},
    {"date": "23.02", "name": "День защитника Отечества (РФ, Беларусь)", "icon": "🎖️", "gender": "Male",
     "remind_days": [7, 2, 0],
     "msg7": "🎖️ Через неделю — 23 Февраля!\nНе забудьте подготовить поздравления для наших мужчин! 🎁",
     "msg2": "🎖️ Послезавтра — День защитника Отечества!\nПодготовьте поздравления! 💪",
     "msgDay": "🎖️ Дорогие мужчины, с праздником!\nСилы, мужества и уверенности!\nС 23 Февраля! 💪"},
    {"date": "08.03", "name": "Международный женский день", "icon": "💐", "gender": "Female",
     "remind_days": [7, 2, 0],
     "msg7": "💐 Через неделю — 8 Марта!\nНе забудьте подготовить поздравления для наших девушек! 🎁",
     "msg2": "💐 Послезавтра — 8 Марта!\nПоследний шанс подготовить поздравления! 🌸",
     "msgDay": "💐 Дорогие девушки, с праздником!\nКрасоты, вдохновения и радости! 🌷\nС 8 Марта! 💕"},
    {"date": "01.05", "name": "Праздник Весны и Труда", "icon": "🌿", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🌿 С Праздником Весны и Труда!\nОтличного настроения и тёплых майских дней!\nС праздником, коллеги! ☀️"},
    {"date": "09.05", "name": "День Победы (РФ, Беларусь)", "icon": "🎖️", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🎖️ Сегодня — День Победы!\nПомним. Гордимся. С праздником, коллеги! 🕯️"},
    {"date": "25.12", "name": "Рождество Христово (Латвия, Беларусь)", "icon": "🎄", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🎄 С Рождеством Христовым!\nТёплого и светлого праздника! ✨"},
    {"date": "12.06", "name": "День России", "icon": "🇷🇺", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🇷🇺 Сегодня — День России!\nС праздником, коллеги! 🎉"},
    {"date": "04.11", "name": "День народного единства", "icon": "🇷🇺", "gender": "all",
     "remind_days": [2, 0], "msgDay": None},
    {"date": "03.04", "name": "Страстная пятница (Латвия)", "icon": "✝️", "gender": "all",
     "remind_days": [0],
     "msgDay": "✝️ Сегодня — Страстная пятница.\nТихого и светлого дня, коллеги. 🙏"},
    {"date": "05.04", "name": "Пасха (Латвия)", "icon": "🥚", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🥚 Светлой Пасхи!\nС праздником, коллеги! 🙏"},
    {"date": "06.04", "name": "Второй день Пасхи (Латвия)", "icon": "🐣", "gender": "all",
     "remind_days": [0],
     "msgDay": "🐣 Второй день Пасхи!\nСветлых праздничных дней, коллеги! 🌷"},
    {"date": "04.05", "name": "День восстановления независимости Латвии", "icon": "🇱🇻", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🇱🇻 Сегодня — День восстановления независимости Латвии!\nС праздником! 🎉"},
    {"date": "10.05", "name": "День матери (Латвия)", "icon": "👩", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "👩 Сегодня — День матери!\nВсем мамам — тепла, любви и благодарности! 💐\nС праздником! 💕"},
    {"date": "23.06", "name": "Лиго (Латвия)", "icon": "🔥", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🔥 Сегодня — Лиго!\nС праздником, коллеги! 🌿🎉"},
    {"date": "24.06", "name": "Янов день (Латвия)", "icon": "🌅", "gender": "all",
     "remind_days": [0],
     "msgDay": "🌅 Сегодня — Янов день!\nС праздником! ☀️"},
    {"date": "18.11", "name": "День провозглашения Латвийской Республики", "icon": "🇱🇻", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🇱🇻 Сегодня — День провозглашения Латвийской Республики!\nС праздником! 🎉"},
    {"date": "24.12", "name": "Сочельник (Латвия)", "icon": "🎄", "gender": "all",
     "remind_days": [0],
     "msgDay": "🎄 Сегодня — Сочельник, канун Рождества!\nУютного и тёплого вечера, коллеги! ✨"},
    {"date": "26.12", "name": "Второй день Рождества (Латвия)", "icon": "🎄", "gender": "all",
     "remind_days": [0],
     "msgDay": "🎄 Второй день Рождества!\nПродолжаем праздновать, коллеги! ✨"},
    {"date": "31.12", "name": "Канун Нового года (Латвия)", "icon": "🎆", "gender": "all",
     "remind_days": [0],
     "msgDay": "🎆 Сегодня — канун Нового года!\nС наступающим, коллеги! Пусть всё задуманное сбудется! 🥂"},
    {"date": "21.04", "name": "Радуница (Беларусь)", "icon": "🕯️", "gender": "all",
     "remind_days": [2, 0], "msgDay": None},
    {"date": "03.07", "name": "День Независимости Беларуси", "icon": "🇧🇾", "gender": "all",
     "remind_days": [2, 0],
     "msgDay": "🇧🇾 Сегодня — День Независимости Беларуси!\nС праздником! 🎉"},
    {"date": "07.11", "name": "День Октябрьской революции (Беларусь)", "icon": "📜", "gender": "all",
     "remind_days": [0], "msgDay": None},
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logic.py::test_holiday_list_has_v4_entries -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/holidays.py tests/test_logic.py
git commit -m "feat: v4 holiday list with Latvian additions"
```

---

## Task 6: Holiday message building

Port of BLOCK 2 of `birthday-code.js`: gendered holidays (build a name list of matching-gender staff, routed per dept/extra/management-with-country) and general holidays (blast unique dept/extra/management chats). Custom `msgDay/msg2/msg7/msg14/msg21` selection by `diffDays`.

**Files:**
- Modify: `app/logic.py`
- Test: `tests/test_logic.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logic.py (append)
from app.logic import build_holiday_messages


def _people():
    return [
        Employee("Иван", "IT", "Энди", "Male", "", "Латвия", "111", "999"),
        Employee("Мария", "IT", "Энди", "Female", "", "Россия", "111", "999"),
    ]


def test_general_holiday_blasts_unique_chats_with_custom_msg():
    today = date(2026, 5, 9)  # День Победы, general, msgDay set
    msgs = build_holiday_messages(_people(), today, MGMT)
    by_chat = {m.chat_id: m.text for m in msgs}
    assert set(by_chat) == {111, 999, MGMT}
    assert by_chat[111] == "🎖️ Сегодня — День Победы!\nПомним. Гордимся. С праздником, коллеги! 🕯️"


def test_gendered_holiday_female_only_with_list():
    today = date(2026, 3, 8)  # 8 марта, Female
    msgs = build_holiday_messages(_people(), today, MGMT)
    by_chat = {m.chat_id: m.text for m in msgs}
    # only the female is listed; management list includes country
    assert "  • Мария" in by_chat[111]
    assert "Иван" not in by_chat[111]
    assert "  • Мария (Россия)" in by_chat[MGMT]
    assert "👥 Поздравляем (1 чел.)" in by_chat[MGMT]


def test_gendered_holiday_advance_prefix_and_gift_line():
    today = date(2026, 2, 16)  # 7 days before 23.02, Male, msg7 set
    msgs = build_holiday_messages(_people(), today, MGMT)
    text = {m.chat_id: m.text for m in msgs}[111]
    assert text.startswith("🎖️ Через неделю — 23 Февраля!")
    assert "  • Иван" in text and "Мария" not in text
    assert text.endswith("Подготовьте поздравления! 🎁")


def test_holiday_no_match_returns_empty():
    assert build_holiday_messages(_people(), date(2026, 7, 15), MGMT) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_logic.py -q`
Expected: FAIL — `cannot import name 'build_holiday_messages'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/logic.py (append)
from app.holidays import HOLIDAYS


def _custom_msg(holiday, d):
    return {
        0: holiday.get("msgDay"),
        2: holiday.get("msg2"),
        7: holiday.get("msg7"),
        14: holiday.get("msg14"),
        21: holiday.get("msg21"),
    }.get(d)


def _advance_prefix(holiday, d):
    if d >= 7:
        word = "три недели" if d == 21 else "две недели" if d == 14 else "неделю"
        return f"📅 Через {word} — {holiday['icon']} {holiday['name']}!"
    return f"⏰ Послезавтра — {holiday['icon']} {holiday['name']}!"


def build_holiday_messages(rows: list[Employee], today, management_chat_id) -> list[Message]:
    results: list[Message] = []
    for holiday in HOLIDAYS:
        hd = parse_ddmm(holiday["date"])
        if not hd:
            continue
        d = diff_days(hd[0], hd[1], today)
        if d not in holiday["remind_days"]:
            continue

        all_dept_chats, all_extra_chats = [], []
        names_by_dept, names_by_extra = {}, {}
        all_names, all_names_country = [], []

        for e in rows:
            if not e.name:
                continue
            if holiday["gender"] != "all" and e.gender != holiday["gender"]:
                continue
            all_names.append(e.name)
            all_names_country.append(f"{e.name} ({e.country})" if e.country else e.name)
            if e.dept_chat_id:
                key = str(e.dept_chat_id).strip()
                if key not in names_by_dept:
                    names_by_dept[key] = []
                    all_dept_chats.append(key)
                names_by_dept[key].append(e.name)
            for extra in e.extra_group_ids():
                if extra not in names_by_extra:
                    names_by_extra[extra] = []
                    all_extra_chats.append(extra)
                names_by_extra[extra].append(e.name)

        custom = _custom_msg(holiday, d)

        if holiday["gender"] != "all":
            if not all_names:
                continue
            if d == 0 and custom:
                for chat, names in names_by_dept.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{custom}\n\nПоздравляем:\n{lst}", chat)
                for chat, names in names_by_extra.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{custom}\n\nПоздравляем:\n{lst}", chat)
                lst = "\n".join(f"  • {n}" for n in all_names_country)
                _add(results, f"{custom}\n\n👥 Поздравляем ({len(all_names)} чел.):\n{lst}", management_chat_id)
            else:
                prefix = custom or _advance_prefix(holiday, d)
                for chat, names in names_by_dept.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{prefix}\n\nПоздравляем:\n{lst}\n\nПодготовьте поздравления! 🎁", chat)
                for chat, names in names_by_extra.items():
                    lst = "\n".join(f"  • {n}" for n in names)
                    _add(results, f"{prefix}\n\nПоздравляем:\n{lst}\n\nПодготовьте поздравления! 🎁", chat)
                lst = "\n".join(f"  • {n}" for n in all_names_country)
                _add(results, f"{prefix}\n\n👥 Поздравляем ({len(all_names)} чел.):\n{lst}\n\nПодготовьте поздравления! 🎁", management_chat_id)
        else:
            if d == 0:
                msg = custom or f"{holiday['icon']} Сегодня — {holiday['name']}!\nС праздником, коллеги! 🎉"
            else:
                msg = custom or _advance_prefix(holiday, d)
            for chat in all_dept_chats:
                _add(results, msg, chat)
            for chat in all_extra_chats:
                _add(results, msg, chat)
            _add(results, msg, management_chat_id)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_logic.py -q`
Expected: PASS (all tests in file).

- [ ] **Step 5: Commit**

```bash
git add app/logic.py tests/test_logic.py
git commit -m "feat: holiday message building (BLOCK 2 port)"
```

---

## Task 7: `build_messages` combiner

Single entry point used by the runner — concatenates birthday + holiday messages.

**Files:**
- Modify: `app/logic.py`
- Test: `tests/test_logic.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_logic.py (append)
from app.logic import build_messages


def test_build_messages_combines_blocks():
    today = date(2026, 6, 10)  # Тимон birthday today
    rows = [_emp(dept_chat_id="", extra_groups="")]
    out = build_messages(rows, today, MGMT)
    assert all(isinstance(m, Message) for m in out)
    assert any("день рождения" in m.text for m in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logic.py::test_build_messages_combines_blocks -q`
Expected: FAIL — `cannot import name 'build_messages'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/logic.py (append)
def build_messages(rows, today, management_chat_id) -> list[Message]:
    return (build_birthday_messages(rows, today, management_chat_id)
            + build_holiday_messages(rows, today, management_chat_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logic.py::test_build_messages_combines_blocks -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/logic.py tests/test_logic.py
git commit -m "feat: build_messages combiner"
```

---

## Task 8: Configuration (`pydantic-settings`)

Matches the fleet's `app/config/settings.py` idiom.

**Files:**
- Create: `app/config/settings.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -q`
Expected: FAIL — `No module named 'app.config.settings'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/config/settings.py
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


settings = Settings()
```

> Note: the module-level `settings = Settings()` will fail at import if required
> env vars are absent. Tests construct `Settings(_env_file=None)` directly and set
> env via monkeypatch, so they never import the module-level singleton. The app
> imports `from app.config.settings import settings` only at runtime (inside the
> container, where `.env` is present).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/config/settings.py tests/test_config.py
git commit -m "feat: pydantic-settings configuration"
```

---

## Task 9: Data source interface + local xlsx reader

**Files:**
- Create: `app/sources/base.py`, `app/sources/local_file.py`
- Test: `tests/test_local_file.py`

The committed test file `dzimsanas dienas - TEST (bez ID).xlsx` is the fixture.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_local_file.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_file.py -q`
Expected: FAIL — `No module named 'app.sources.local_file'`.

- [ ] **Step 3: Write the interface**

```python
# app/sources/base.py
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
```

- [ ] **Step 4: Write the local reader**

```python
# app/sources/local_file.py
from __future__ import annotations
import openpyxl
from app.models import Employee
from app.sources.base import COLUMNS, row_to_employee


class LocalFileSource:
    def __init__(self, path: str, sheet: str = "Sheet1"):
        self.path = path
        self.sheet = sheet

    def load(self) -> list[Employee]:
        wb = openpyxl.load_workbook(self.path, data_only=True)
        ws = wb[self.sheet] if self.sheet in wb.sheetnames else wb.worksheets[0]
        header = [c.value for c in ws[1]]
        out: list[Employee] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            record = {header[i]: row[i] for i in range(len(header)) if header[i] in COLUMNS}
            emp = row_to_employee(record)
            if emp:
                out.append(emp)
        return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_local_file.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/sources/base.py app/sources/local_file.py tests/test_local_file.py
git commit -m "feat: data source interface + local xlsx reader"
```

---

## Task 10: Google Sheets reader + source factory

`GoogleSheetsSource` reuses `row_to_employee`. Tested with an injected fake client (no live credentials). `get_source(settings)` picks the implementation.

**Files:**
- Create: `app/sources/google_sheets.py`
- Modify: `app/sources/base.py` (add `get_source`)
- Test: `tests/test_sources_factory.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sources_factory.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sources_factory.py -q`
Expected: FAIL — `No module named 'app.sources.google_sheets'`.

- [ ] **Step 3: Write the Google Sheets reader**

```python
# app/sources/google_sheets.py
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
```

- [ ] **Step 4: Add the factory to `base.py`**

```python
# app/sources/base.py (append)
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_sources_factory.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/sources/google_sheets.py app/sources/base.py tests/test_sources_factory.py
git commit -m "feat: google sheets reader + source factory"
```

---

## Task 11: Telegram sender

`send_all` sends each `Message` via an aiogram `Bot`, captures per-message failures, and returns a `SendReport`. A small delay between sends respects Telegram rate limits. Tested with a fake bot.

**Files:**
- Create: `app/telegram.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_telegram.py
import pytest
from app.models import Message
from app.telegram import send_all, SendReport


class _FakeBot:
    def __init__(self, fail_chat_ids=()):
        self.sent = []
        self.fail = set(fail_chat_ids)
    async def send_message(self, chat_id, text):
        if chat_id in self.fail:
            raise RuntimeError("403 Forbidden")
        self.sent.append((chat_id, text))


async def test_send_all_sends_every_message():
    bot = _FakeBot()
    msgs = [Message(1, "a"), Message(2, "b")]
    report = await send_all(bot, msgs, delay=0)
    assert report.sent == 2 and report.failed == 0
    assert bot.sent == [(1, "a"), (2, "b")]


async def test_send_all_continues_on_failure():
    bot = _FakeBot(fail_chat_ids={2})
    msgs = [Message(1, "a"), Message(2, "b"), Message(3, "c")]
    report = await send_all(bot, msgs, delay=0)
    assert report.sent == 2 and report.failed == 1
    assert 2 in [cid for cid, _ in report.failures]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram.py -q`
Expected: FAIL — `No module named 'app.telegram'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/telegram.py
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from app.models import Message

logger = logging.getLogger(__name__)


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0
    failures: list = field(default_factory=list)  # list[(chat_id, error_str)]


async def send_all(bot, messages: list[Message], delay: float = 0.05) -> SendReport:
    report = SendReport()
    for m in messages:
        try:
            await bot.send_message(chat_id=m.chat_id, text=m.text)
            report.sent += 1
        except Exception as e:  # noqa: BLE001 — one failure must not stop the run
            report.failed += 1
            report.failures.append((m.chat_id, str(e)))
            logger.error("send to %s failed: %s", m.chat_id, e)
        if delay:
            await asyncio.sleep(delay)
    return report
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telegram.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/telegram.py tests/test_telegram.py
git commit -m "feat: telegram send_all with per-message error capture"
```

---

## Task 12: Scheduler — next-run calc + state dedupe

Pure `next_run_at(now, run_time, tz)` for the sleep duration, and a state file so a same-day container restart doesn't re-send.

**Files:**
- Create: `app/scheduler.py`
- Test: `tests/test_scheduler.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scheduler.py
from datetime import datetime
from zoneinfo import ZoneInfo
from app.scheduler import next_run_at, already_ran_today, mark_ran_today

TZ = "Asia/Tbilisi"


def test_next_run_is_later_today_when_before_run_time():
    now = datetime(2026, 6, 3, 7, 0, tzinfo=ZoneInfo(TZ))
    nxt = next_run_at(now, "09:00", TZ)
    assert nxt.hour == 9 and nxt.day == 3


def test_next_run_is_tomorrow_when_past_run_time():
    now = datetime(2026, 6, 3, 10, 0, tzinfo=ZoneInfo(TZ))
    nxt = next_run_at(now, "09:00", TZ)
    assert nxt.day == 4 and nxt.hour == 9


def test_state_roundtrip(tmp_path):
    state = str(tmp_path / "state.json")
    today = "2026-06-03"
    assert already_ran_today(state, today) is False
    mark_ran_today(state, today)
    assert already_ran_today(state, today) is True
    assert already_ran_today(state, "2026-06-04") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scheduler.py -q`
Expected: FAIL — `No module named 'app.scheduler'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/scheduler.py
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def next_run_at(now: datetime, run_time: str, tz: str) -> datetime:
    hh, mm = (int(x) for x in run_time.split(":"))
    zone = ZoneInfo(tz)
    now = now.astimezone(zone)
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _read(state_file: str) -> dict:
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def already_ran_today(state_file: str, today_iso: str) -> bool:
    return _read(state_file).get("last_run") == today_iso


def mark_ran_today(state_file: str, today_iso: str) -> None:
    os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"last_run": today_iso}, f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scheduler.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/scheduler.py tests/test_scheduler.py
git commit -m "feat: scheduler next-run calc + state dedupe"
```

---

## Task 13: Runner — orchestrate a daily run

`run_daily()` wires source → logic → telegram → admin report → state. Takes injectable dependencies for testing.

**Files:**
- Create: `app/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runner.py
from datetime import date
from app.models import Employee, Message
from app.runner import run_daily


class _FakeBot:
    def __init__(self):
        self.sent = []
    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class _FakeSource:
    def __init__(self, rows):
        self._rows = rows
    def load(self):
        return self._rows


async def test_run_daily_sends_and_reports(tmp_path):
    rows = [Employee("Тимон", "IT", "Энди", "Male", "10.06", "Латвия", "111", "")]
    bot = _FakeBot()
    state = str(tmp_path / "state.json")
    report = await run_daily(
        bot=bot, source=_FakeSource(rows), today=date(2026, 6, 10),
        management_chat_id=999, admin_chat_id=500, state_file=state, delay=0,
    )
    # birthday today -> dept(111) + management(999) + admin summary(500)
    chat_ids = [cid for cid, _ in bot.sent]
    assert 111 in chat_ids and 999 in chat_ids
    assert 500 in chat_ids  # admin summary
    assert report.sent >= 2


async def test_run_daily_admin_alert_on_source_error(tmp_path):
    class _BoomSource:
        def load(self):
            raise RuntimeError("sheet unreachable")
    bot = _FakeBot()
    state = str(tmp_path / "state.json")
    await run_daily(bot=bot, source=_BoomSource(), today=date(2026, 6, 10),
                    management_chat_id=999, admin_chat_id=500, state_file=state, delay=0)
    # admin got an error alert
    assert any(cid == 500 and "❌" in text for cid, text in bot.sent)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runner.py -q`
Expected: FAIL — `No module named 'app.runner'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/runner.py
from __future__ import annotations
import logging
from datetime import date
from app.logic import build_messages
from app.telegram import send_all
from app.scheduler import mark_ran_today

logger = logging.getLogger(__name__)


async def run_daily(*, bot, source, today: date, management_chat_id: int,
                    admin_chat_id: int, state_file: str, delay: float = 0.05):
    try:
        rows = source.load()
    except Exception as e:  # noqa: BLE001
        logger.exception("data source load failed")
        try:
            await bot.send_message(chat_id=admin_chat_id,
                                   text=f"❌ Бот ДР: источник данных недоступен: {e}")
        except Exception:
            logger.exception("admin alert failed")
        return None

    messages = build_messages(rows, today, management_chat_id)
    report = await send_all(bot, messages, delay=delay)

    summary = f"✅ Бот ДР {today.isoformat()}: отправлено {report.sent}"
    if report.failed:
        ids = ", ".join(str(cid) for cid, _ in report.failures)
        summary += f"\n⚠️ не доставлено {report.failed} (chat ids: {ids})"
    try:
        await bot.send_message(chat_id=admin_chat_id, text=summary)
    except Exception:
        logger.exception("admin summary failed")

    mark_ran_today(state_file, today.isoformat())
    return report
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runner.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/runner.py tests/test_runner.py
git commit -m "feat: daily run orchestration with admin reporting"
```

---

## Task 14: FastAPI app — `/health`, `/run`, scheduler loop

Matches the fleet's `lifespan` + `asyncio` loop idiom. The loop sleeps until `next_run_at`, runs (guarded by the state file), repeats. `POST /run` triggers an immediate run for testing. `RUN_ON_START` runs once at boot.

**Files:**
- Create: `app/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
import os
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
            class M: username = "birthdays_sport_bot"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -q`
Expected: FAIL — `No module named 'app.main'`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/main.py
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from aiogram import Bot

from app.config.settings import settings
from app.sources.base import get_source
from app.runner import run_daily
from app.scheduler import next_run_at, already_ran_today

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("birthday-bot")

SCHEDULER_ENABLED = True


def make_bot(token: str) -> Bot:
    return Bot(token=token)


async def _do_run():
    bot = make_bot(settings.telegram_bot_token)
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    try:
        await run_daily(
            bot=bot,
            source=get_source(settings),
            today=today,
            management_chat_id=settings.management_chat_id,
            admin_chat_id=settings.admin_chat_id,
            state_file=settings.state_file,
        )
    finally:
        close = getattr(getattr(bot, "session", None), "close", None)
        if close:
            await close()


async def scheduler_loop():
    while SCHEDULER_ENABLED:
        now = datetime.now(ZoneInfo(settings.timezone))
        nxt = next_run_at(now, settings.run_time, settings.timezone)
        sleep_s = (nxt - now).total_seconds()
        logger.info("next run at %s (in %.0f min)", nxt.isoformat(), sleep_s / 60)
        await asyncio.sleep(sleep_s)
        today_iso = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
        if not already_ran_today(settings.state_file, today_iso):
            await _do_run()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_on_start:
        await _do_run()
    task = asyncio.create_task(scheduler_loop()) if SCHEDULER_ENABLED else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Birthday & Holiday Bot", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run_now():
    await _do_run()
    return {"status": "done"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -q`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `pytest -q`
Expected: PASS (all tests across all files).

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: FastAPI app with /health, /run, daily scheduler loop"
```

---

## Task 15: Docker, compose, env example, README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`

- [ ] **Step 1: Write `Dockerfile`** (same shape as the fleet)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `docker-compose.yml`** (single service, host port 8002, /data volume)

```yaml
services:
  app:
    build: .
    ports:
      - "8002:8000"
    env_file:
      - .env
    volumes:
      - ./data:/data
    restart: unless-stopped
```

- [ ] **Step 3: Write `.env.example`**

```
# Copy to .env and fill in real values on the server. Never commit .env.

# Telegram — @birthdays_sport_bot token
TELEGRAM_BOT_TOKEN=

# Management chat (gets ALL notifications, with country)
MANAGEMENT_CHAT_ID=

# Admin chat for run summaries / error alerts (your own Telegram ID for testing)
ADMIN_CHAT_ID=6091784070

# Scheduling
TIMEZONE=Asia/Tbilisi
RUN_TIME=09:00
RUN_ON_START=false

# Data source: "local" (xlsx) for testing, "gsheets" for production
DATA_SOURCE=local
DATA_FILE=/data/employees.xlsx
STATE_FILE=/data/state.json

# Google Sheets (only when DATA_SOURCE=gsheets)
GOOGLE_CREDENTIALS_JSON=/data/gcreds.json
GSHEET_ID=
GSHEET_TAB=Sheet1
```

- [ ] **Step 4: Write `README.md`**

````markdown
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
````

- [ ] **Step 5: Verify the image builds and compose config is valid**

Run:
```bash
docker compose config >/dev/null && echo "compose OK"
docker compose build 2>&1 | tail -3
```
Expected: "compose OK" and a successful build (ends with naming/exporting the image).

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .env.example README.md
git commit -m "feat: Docker, compose, env example, README"
```

---

## Task 16: Local end-to-end test send

Final verification — a real send to the test ID via the running container.

**Files:** none (operational)

- [ ] **Step 1: Prepare `.env` and data**

```bash
cp .env.example .env
# edit .env: set TELEGRAM_BOT_TOKEN, MANAGEMENT_CHAT_ID=6091784070, ADMIN_CHAT_ID=6091784070
mkdir -p data && cp "dzimsanas dienas - TEST (bez ID).xlsx" data/employees.xlsx
```

- [ ] **Step 2: Build and start**

Run: `docker compose up -d --build`
Expected: container `Up`.

- [ ] **Step 3: Trigger a run and observe**

Run: `curl -X POST http://localhost:8002/run`
Expected: `{"status":"done"}`, and an admin summary message arrives in Telegram
(`✅ Бот ДР … отправлено N`). If any chat 403s, it's listed in the summary.

- [ ] **Step 4: Confirm dedupe + scheduler**

Run: `docker compose logs --tail=20 app`
Expected: a log line `next run at <tomorrow 09:00> …`. A second `POST /run` still
sends (manual trigger bypasses dedupe); the *scheduled* path is guarded by
`state.json`.

- [ ] **Step 5: Push the branch**

```bash
git push origin main
```

---

## Self-Review

**Spec coverage:**
- §3 Stack → Tasks 1, 8, 14, 15 ✓
- §4/§5 Architecture & components → Tasks 8–14 (one task per module) ✓
- §6 Config → Task 8 + Task 15 `.env.example` ✓
- §7 Logic port (identical messages, v4 holidays, numeric date handling) → Tasks 2, 4, 5, 6, 7 ✓
- §8 Reliability (dedupe, per-message resilience, admin report) → Tasks 11, 12, 13 ✓
- §9 Telegram prerequisites → README (Task 15) ✓
- §10 Testing (logic exact-output, sources, e2e) → Tasks 4–7, 9, 16 ✓
- §11 Deployment + cutover → Tasks 15, 16 ✓

**Placeholder scan:** No TBD/TODO; every code step contains full code; every test has assertions. ✓

**Type consistency:** `Employee`/`Message` (Task 3) used consistently; `build_messages(rows, today, management_chat_id)` signature matches across Tasks 4–7, 13; `send_all(bot, messages, delay)` consistent (Tasks 11, 13); `run_daily(...)` keyword args consistent (Tasks 13, 14); `get_source(settings)` consistent (Tasks 10, 14). ✓
