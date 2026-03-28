# Badminton Slot Notifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that checks Tower Hamlets Council badminton court availability and sends Telegram notifications when slots match user-defined rules.

**Architecture:** Single Python script with modular functions: one to obtain a fresh JWT via Playwright, one to query the sessions API, one to filter slots against rules, and one to send Telegram notifications. A JSON config file drives behavior. A lightweight dedup mechanism (JSON file) prevents repeat notifications.

**Tech Stack:** Python 3.11+, `uv` for package management, `httpx` for HTTP, `playwright` for JWT acquisition, Telegram Bot API via `httpx`

---

## API Research Summary

### Authentication
- Navigate to `https://towerhamletscouncil.gladstonego.cloud/book` to get a `Jwt` cookie (anonymous session)
- All API calls require `Cookie: Jwt=<token>` and header `x-use-sso: 1`
- JWT expires (observed ~24h), must be refreshed before each run

### Sessions API
- **URL:** `GET /api/availability/V2/sessions`
- **Params:** `webBookableOnly=true`, `siteIds=<comma-separated>`, `activityIds=<comma-separated>`, `dateFrom=<ISO8601>`
- **Single call** returns ALL days from `dateFrom` through ~81 days out
- **Multi-site + multi-activity** works in one call (comma-separated)

### Response Structure
```
Array of objects, one per activity-per-date:
{
  "id": "JACT000010",           // activity ID
  "name": "Badminton 40 Mins",  // activity name
  "date": "2026-03-29",         // date string
  "siteId": "JOSC",             // venue ID
  "locations": [
    {
      "locationNameToDisplay": "John Orwell Court 1",
      "slots": [
        {
          "startTime": "2026-03-29T08:40:00Z",
          "endTime": "2026-03-29T09:19:59Z",
          "status": "Available" | "Unavailable",
          "availability": { "inCentre": 1, "virtual": 0 }
        }
      ]
    }
  ]
}
```

### Availability Indicator
- `slot.status === "Available"` means bookable
- `slot.availability.inCentre > 0` also indicates availability (redundant with status)

### Cached Constants

**Sites:**
| ID | Name |
|----|------|
| JOSC | John Orwell |
| MEPLS | Mile End Park Leisure Centre |
| PBLC | Poplar Baths Leisure Centre |
| WSC | Whitechapel Sports Centre |

**Badminton Activity IDs:**
| Site | 40 Mins | 60 Mins |
|------|---------|---------|
| JOSC | JACT000010 | JACT000011 |
| MEPLS | MACT000009, MACT000010 | MACT000011 |
| PBLC | PACT000010 | PACT000011 |
| WSC | WACT000010 | WACT000011 |

---

## File Structure

```
badminton/
├── pyproject.toml            # uv project config with dependencies
├── config.json               # user config (rules, telegram settings, sites)
├── src/
│   ├── __init__.py
│   ├── main.py               # entry point, orchestrates the flow
│   ├── auth.py               # JWT acquisition via playwright
│   ├── api.py                # sessions API client
│   ├── filters.py            # rule matching logic
│   ├── notify.py             # Telegram notification sender
│   └── dedup.py              # deduplication to avoid repeat notifications
├── notified.json             # runtime: tracks already-notified slots (gitignored)
└── tests/
    ├── __init__.py
    ├── test_filters.py       # unit tests for rule matching
    └── test_dedup.py         # unit tests for dedup logic
```

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `config.json`
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Initialize uv project**

```bash
cd /Users/harsh/dev/badminton
uv init --name badminton-notifier
```

- [ ] **Step 2: Add dependencies**

```bash
uv add httpx playwright
uv add --dev pytest
```

- [ ] **Step 3: Install playwright browsers**

```bash
uv run playwright install chromium
```

- [ ] **Step 4: Create directory structure**

```bash
mkdir -p src tests
touch src/__init__.py tests/__init__.py
```

- [ ] **Step 5: Create .gitignore**

```
notified.json
.playwright-cli/
__pycache__/
.venv/
```

- [ ] **Step 6: Create config.json with example configuration**

```json
{
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "sites": {
    "JOSC": "John Orwell",
    "MEPLS": "Mile End Park Leisure Centre",
    "PBLC": "Poplar Baths Leisure Centre",
    "WSC": "Whitechapel Sports Centre"
  },
  "activities": {
    "JACT000010": {"name": "Badminton 40 Mins", "site": "JOSC"},
    "JACT000011": {"name": "Badminton 60 Mins", "site": "JOSC"},
    "MACT000009": {"name": "Badminton 40 Mins", "site": "MEPLS"},
    "MACT000010": {"name": "Badminton 40 Mins", "site": "MEPLS"},
    "MACT000011": {"name": "Badminton 60 Mins", "site": "MEPLS"},
    "PACT000010": {"name": "Badminton 40 Mins", "site": "PBLC"},
    "PACT000011": {"name": "Badminton 60 Mins", "site": "PBLC"},
    "WACT000010": {"name": "Badminton 40 Mins", "site": "WSC"},
    "WACT000011": {"name": "Badminton 60 Mins", "site": "WSC"}
  },
  "check_days": 7,
  "rules": [
    {"days": ["sat", "sun"], "start": "08:00", "end": "22:00"},
    {"days": ["mon", "tue", "wed", "thu", "fri"], "start": "17:00", "end": "22:00"}
  ]
}
```

**Rules semantics:** Each rule specifies days-of-week and a time window. A slot matches if its day matches any in `days` AND its start time is >= `start` AND < `end`. Rules are OR'd: if ANY rule matches, the slot is notified. Empty rules array = notify all available slots. Optional fields: `sites` (list of site IDs to restrict), `activity` ("40" or "60" to restrict duration).

- [ ] **Step 7: Commit**

```bash
git init && git add -A && git commit -m "chore: project setup with uv, config, and structure"
```

---

## Task 2: Authentication Module

**Files:**
- Create: `src/auth.py`

- [ ] **Step 1: Implement JWT acquisition**

```python
import httpx
from playwright.sync_api import sync_playwright


BASE_URL = "https://towerhamletscouncil.gladstonego.cloud"


def get_jwt() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{BASE_URL}/book")
        page.wait_for_load_state("networkidle")

        cookies = context.cookies()
        jwt_cookie = next((c for c in cookies if c["name"] == "Jwt"), None)
        browser.close()

        if not jwt_cookie:
            raise RuntimeError("Failed to obtain JWT cookie")
        return jwt_cookie["value"]
```

- [ ] **Step 2: Verify it works**

```bash
uv run python -c "from src.auth import get_jwt; print(get_jwt()[:50])"
```

Expected: prints first 50 chars of a JWT token starting with `eyJ`

- [ ] **Step 3: Commit**

```bash
git add src/auth.py && git commit -m "feat: add JWT acquisition via playwright"
```

---

## Task 3: API Client Module

**Files:**
- Create: `src/api.py`

- [ ] **Step 1: Implement sessions API client**

```python
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

import httpx


BASE_URL = "https://towerhamletscouncil.gladstonego.cloud"


@dataclass(frozen=True)
class Slot:
    activity_name: str
    site_id: str
    site_name: str
    location: str
    date: str
    start_time: str
    end_time: str


def fetch_available_slots(jwt: str, config: dict) -> list[Slot]:
    activity_ids = ",".join(config["activities"].keys())
    site_ids = ",".join(config["sites"].keys())
    date_from = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")

    url = f"{BASE_URL}/api/availability/V2/sessions"
    params = {
        "webBookableOnly": "true",
        "siteIds": site_ids,
        "activityIds": activity_ids,
        "dateFrom": date_from,
    }
    headers = {
        "accept": "application/json",
        "x-use-sso": "1",
    }
    cookies = {"Jwt": jwt}

    resp = httpx.get(url, params=params, headers=headers, cookies=cookies, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    cutoff_date = (datetime.now(timezone.utc) + timedelta(days=config["check_days"])).strftime("%Y-%m-%d")

    slots: list[Slot] = []
    for activity in data:
        if activity["date"] > cutoff_date:
            continue
        for loc in activity["locations"]:
            for slot in loc["slots"]:
                if slot["status"] != "Available":
                    continue
                site_name = config["sites"].get(activity["siteId"], activity["siteId"])
                slots.append(Slot(
                    activity_name=activity["name"],
                    site_id=activity["siteId"],
                    site_name=site_name,
                    location=loc["locationNameToDisplay"],
                    date=activity["date"],
                    start_time=slot["startTime"],
                    end_time=slot["endTime"],
                ))
    return slots
```

- [ ] **Step 2: Verify it works**

```bash
uv run python -c "
from src.auth import get_jwt
from src.api import fetch_available_slots
import json

config = json.load(open('config.json'))
jwt = get_jwt()
slots = fetch_available_slots(jwt, config)
print(f'Found {len(slots)} available slots')
for s in slots[:5]:
    print(f'  {s.date} {s.start_time} - {s.activity_name} @ {s.site_name} {s.location}')
"
```

Expected: prints count and first few available slots

- [ ] **Step 3: Commit**

```bash
git add src/api.py && git commit -m "feat: add sessions API client with slot extraction"
```

---

## Task 4: Filter Module

**Files:**
- Create: `src/filters.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing tests for filter logic**

```python
from datetime import datetime
from src.filters import matches_rules
from src.api import Slot


def _slot(day_name: str, hour: int, minute: int = 0) -> Slot:
    """Helper to create a Slot on a specific day-of-week and time."""
    # Find next occurrence of the given day
    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    target = day_map[day_name]
    today = datetime.now()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    d = today.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    d = d + timedelta(days=days_ahead)
    date_str = d.strftime("%Y-%m-%d")
    start = f"{date_str}T{hour:02d}:{minute:02d}:00Z"
    end = f"{date_str}T{hour:02d}:{minute + 39}:59Z"
    return Slot(
        activity_name="Badminton 40 Mins",
        site_id="JOSC",
        site_name="John Orwell",
        location="Court 1",
        date=date_str,
        start_time=start,
        end_time=end,
    )


def test_empty_rules_matches_everything():
    slot = _slot("mon", 10)
    assert matches_rules(slot, []) is True


def test_day_and_time_match():
    rules = [{"days": ["mon"], "start": "09:00", "end": "18:00"}]
    slot = _slot("mon", 10)
    assert matches_rules(slot, rules) is True


def test_day_matches_time_does_not():
    rules = [{"days": ["mon"], "start": "17:00", "end": "22:00"}]
    slot = _slot("mon", 10)
    assert matches_rules(slot, rules) is False


def test_day_does_not_match():
    rules = [{"days": ["sat", "sun"], "start": "08:00", "end": "22:00"}]
    slot = _slot("wed", 10)
    assert matches_rules(slot, rules) is False


def test_multiple_rules_or_logic():
    rules = [
        {"days": ["sat"], "start": "08:00", "end": "12:00"},
        {"days": ["mon"], "start": "17:00", "end": "22:00"},
    ]
    slot_sat_morning = _slot("sat", 9)
    slot_mon_evening = _slot("mon", 18)
    slot_mon_morning = _slot("mon", 9)
    assert matches_rules(slot_sat_morning, rules) is True
    assert matches_rules(slot_mon_evening, rules) is True
    assert matches_rules(slot_mon_morning, rules) is False


def test_site_filter():
    rules = [{"days": ["mon"], "start": "09:00", "end": "22:00", "sites": ["PBLC"]}]
    slot_josc = _slot("mon", 10)  # site_id is JOSC
    assert matches_rules(slot_josc, rules) is False


def test_activity_filter_40():
    rules = [{"days": ["mon"], "start": "09:00", "end": "22:00", "activity": "40"}]
    slot = _slot("mon", 10)  # activity_name is "Badminton 40 Mins"
    assert matches_rules(slot, rules) is True


def test_activity_filter_60_no_match():
    rules = [{"days": ["mon"], "start": "09:00", "end": "22:00", "activity": "60"}]
    slot = _slot("mon", 10)  # activity_name is "Badminton 40 Mins"
    assert matches_rules(slot, rules) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_filters.py -v
```

Expected: FAIL with `ImportError` (filters module doesn't exist yet)

- [ ] **Step 3: Implement filter logic**

```python
from datetime import datetime, timezone

from src.api import Slot


DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def matches_rules(slot: Slot, rules: list[dict]) -> bool:
    if not rules:
        return True

    slot_dt = datetime.fromisoformat(slot.start_time.replace("Z", "+00:00"))
    slot_day = slot_dt.weekday()
    slot_time = slot_dt.strftime("%H:%M")

    for rule in rules:
        rule_days = {DAY_NAMES[d] for d in rule["days"]}
        if slot_day not in rule_days:
            continue

        if not (rule["start"] <= slot_time < rule["end"]):
            continue

        if "sites" in rule and slot.site_id not in rule["sites"]:
            continue

        if "activity" in rule:
            if rule["activity"] not in slot.activity_name:
                continue

        return True

    return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_filters.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/filters.py tests/test_filters.py && git commit -m "feat: add rule-based slot filtering with tests"
```

---

## Task 5: Deduplication Module

**Files:**
- Create: `src/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

```python
import json
import os
from src.dedup import DedupStore
from src.api import Slot


def _slot(start: str = "2026-03-29T10:00:00Z") -> Slot:
    return Slot(
        activity_name="Badminton 40 Mins",
        site_id="JOSC",
        site_name="John Orwell",
        location="Court 1",
        date="2026-03-29",
        start_time=start,
        end_time="2026-03-29T10:39:59Z",
    )


def test_new_slot_is_not_seen(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    slot = _slot()
    assert store.is_seen(slot) is False


def test_mark_and_check(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    slot = _slot()
    store.mark_seen([slot])
    assert store.is_seen(slot) is True


def test_different_slots_are_independent(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    slot1 = _slot("2026-03-29T10:00:00Z")
    slot2 = _slot("2026-03-29T11:00:00Z")
    store.mark_seen([slot1])
    assert store.is_seen(slot1) is True
    assert store.is_seen(slot2) is False


def test_persistence(tmp_path):
    path = tmp_path / "notified.json"
    store1 = DedupStore(path)
    slot = _slot()
    store1.mark_seen([slot])

    store2 = DedupStore(path)
    assert store2.is_seen(slot) is True


def test_cleanup_old_entries(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    old_slot = _slot("2020-01-01T10:00:00Z")
    store.mark_seen([old_slot])
    store.cleanup()
    assert store.is_seen(old_slot) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement dedup logic**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from src.api import Slot


class DedupStore:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._seen: set[str] = set()
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self._seen = set(data)

    @staticmethod
    def _key(slot: Slot) -> str:
        return f"{slot.site_id}|{slot.location}|{slot.start_time}"

    def is_seen(self, slot: Slot) -> bool:
        return self._key(slot) in self._seen

    def mark_seen(self, slots: list[Slot]) -> None:
        for slot in slots:
            self._seen.add(self._key(slot))
        self._save()

    def cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        to_remove = set()
        for key in self._seen:
            try:
                ts = key.rsplit("|", 1)[1]
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt < now:
                    to_remove.add(key)
            except (ValueError, IndexError):
                to_remove.add(key)
        self._seen -= to_remove
        self._save()

    def _save(self) -> None:
        self._path.write_text(json.dumps(sorted(self._seen)))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dedup.py tests/test_dedup.py && git commit -m "feat: add slot deduplication with persistence and cleanup"
```

---

## Task 6: Telegram Notification Module

**Files:**
- Create: `src/notify.py`

- [ ] **Step 1: Implement Telegram notifier**

```python
from src.api import Slot

import httpx


def format_slot_message(slots: list[Slot]) -> str:
    if not slots:
        return ""

    lines = ["🏸 *Badminton Slots Available!*\n"]
    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        key = f"{slot.date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        day_slots = grouped[key]
        dt = __import__("datetime").datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"📅 *{day_label} — {site_name}*")
        for s in sorted(day_slots, key=lambda x: x.start_time):
            start = s.start_time[11:16]
            end = s.end_time[11:16]
            lines.append(f"  • {start}–{end} | {s.activity_name} | {s.location}")
        lines.append("")

    return "\n".join(lines)


def send_telegram(message: str, bot_token: str, chat_id: str) -> None:
    if not message:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    # Telegram has a 4096 char limit per message
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        }, timeout=10)
        resp.raise_for_status()
```

- [ ] **Step 2: Commit**

```bash
git add src/notify.py && git commit -m "feat: add Telegram notification with grouped formatting"
```

---

## Task 7: Main Orchestrator

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement main entry point**

```python
import json
import sys
from pathlib import Path

from src.auth import get_jwt
from src.api import fetch_available_slots
from src.filters import matches_rules
from src.dedup import DedupStore
from src.notify import format_slot_message, send_telegram


def main() -> None:
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text())
    rules = config.get("rules", [])
    telegram = config["telegram"]

    print("Obtaining JWT...")
    jwt = get_jwt()

    print("Fetching available slots...")
    all_slots = fetch_available_slots(jwt, config)
    print(f"  Found {len(all_slots)} available slots total")

    matching = [s for s in all_slots if matches_rules(s, rules)]
    print(f"  {len(matching)} match configured rules")

    dedup_path = Path(__file__).parent.parent / "notified.json"
    store = DedupStore(dedup_path)
    store.cleanup()

    new_slots = [s for s in matching if not store.is_seen(s)]
    print(f"  {len(new_slots)} are new (not previously notified)")

    if new_slots:
        message = format_slot_message(new_slots)
        print("Sending Telegram notification...")
        send_telegram(message, telegram["bot_token"], telegram["chat_id"])
        store.mark_seen(new_slots)
        print("Done!")
    else:
        print("No new slots to notify about.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it runs (dry run — will fail at Telegram unless configured)**

```bash
uv run python -m src.main
```

Expected: prints slot counts, may fail at Telegram step if not configured — that's OK.

- [ ] **Step 3: Commit**

```bash
git add src/main.py && git commit -m "feat: add main orchestrator tying all modules together"
```

---

## Task 8: Run All Tests and Final Verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 2: Run the checker end-to-end (without Telegram)**

```bash
uv run python -c "
from src.auth import get_jwt
from src.api import fetch_available_slots
from src.filters import matches_rules
import json

config = json.load(open('config.json'))
jwt = get_jwt()
slots = fetch_available_slots(jwt, config)
matching = [s for s in slots if matches_rules(s, config.get('rules', []))]
print(f'Total available: {len(slots)}')
print(f'Matching rules: {len(matching)}')
for s in matching[:10]:
    print(f'  {s.date} {s.start_time[11:16]} {s.activity_name} @ {s.site_name} {s.location}')
"
```

- [ ] **Step 3: Final commit**

```bash
git add -A && git commit -m "chore: final verification - all tests passing"
```
