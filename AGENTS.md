# Agent context: badminton-notifier

## 1. Project overview

**badminton-notifier** polls Tower Hamlets council leisure centres (GladstoneGo) for badminton court availability and can alert via Telegram. It filters slots against configurable day/time rules, persists state in SQLite to detect **new**, **gone**, and **now bookable** changes, and formats output for the console or Telegram (MarkdownV2).

- **Runtime**: Python ≥ 3.11
- **Package manager**: [uv](https://github.com/astral-sh/uv) (`pyproject.toml`, `uv.lock`). Install with `uv sync`; run with `uv run …`.
- **Runtime dependency**: `httpx` only (anonymous JWT via HTTP GET; no browser automation).
- **Dev dependency**: `pytest` (dev group).

**Entry points**

- Console script: `badminton-notifier` (defined in `pyproject.toml` as `src.main:main`).
- From repo root: `uv run main.py` (thin wrapper that calls `src.main.main`).

**Configuration**

- Copy `config.example.json` → `config.json` (gitignored). Holds `telegram`, `sites`, `activities`, `check_days`, and optional `rules` for time-of-day / day-of-week filtering.
- **Do not commit** real tokens or `config.json`.

**Data files**

- `slots.db` at **project root** (gitignored): SQLite state for diffing and `cleanup`.

## 2. Architecture notes

**High-level flow**

1. Load `config.json` from project root (`src/main.py`: `PROJECT_ROOT` is parent of `src/`).
2. `get_jwt()` — `GET` `{BASE_URL}/api/samlauthentication/anonymous` with redirects; read `Jwt` cookie (`src/api.py`).
3. `fetch_available_slots()` — `GET` `/api/availability/V2/sessions` with `Jwt` cookie, `x-use-sso: 1`, site/activity IDs from config; only `status == "Available"` rows become `Slot` instances (`src/api.py`).
4. `matches_rules()` — filter slots in **Europe/London** local time (`src/filters.py`); rules can narrow by `sites` and `activity` substring.
5. For commands that diff: load stored rows in date range, `compute_changes()`, optionally `SlotDB.sync()` (`src/diff.py`, `src/db.py`).

**Time zones**

- API slot times are **UTC** ISO strings; parsing uses `Z` → offset (`src/tz.py`: `parse_utc`).
- Display and rule matching use **`Europe/London`** (`to_local`).

**SQLite model** (`src/db.py`)

- Table `slots`; primary key `(site_id, location, start_time)`.
- Tracks `status` (`available` / `unavailable`), `notified_bookable`, and timestamps for “first seen” / updates.
- `sync()` upserts fresh API slots and applies updates for `gone` / `bookable` changes from `compute_changes()`.

**Change semantics** (`src/diff.py`)

- **new**: key absent in DB or row was `unavailable`.
- **gone**: was `available` in DB but not in current API set.
- **bookable**: row exists, `notified_bookable` is false, `bookable_from` parses to ≤ now (UTC).

**Notifications** (`src/notify.py`)

- Telegram: `send_telegram()` posts with `parse_mode: "MarkdownV2"`; long messages split at 4000 chars.
- **Court coalescing**: slots with the same sort key `(start_time, end_time, activity_name)` merge locations when they match `…Court N` pattern (e.g. “Court 1, 3, 4”). Same idea for change lists via `_coalesce_changes`.

**CLI** (`src/main.py`)

| Command | Behaviour |
|--------|-----------|
| *(no subcommand)* | Same as `check` |
| `list` | Fetch, filter, print slots (no DB write) |
| `check` | Diff + sync DB; `--dry-run` skips `sync` |
| `notify current` | Full slot list to Telegram |
| `notify changes` | Diff + sync, then Telegram if there are changes |
| `cleanup N` | Delete rows with `date` older than N days (UTC date string compare) |
| `cleanup --all` | Delete all rows; mutually exclusive with `N` |

**Constants**

- `src/constants.py`: `BASE_URL = "https://towerhamletscouncil.gladstonego.cloud"`.

**Import style**

- Application code uses package imports from repo root: `from src.api import …` (run as installed package or `uv run main.py` from root).

## 3. Testing expectations

- Framework: **pytest** (`uv run pytest` or `uv run python -m pytest`).
- Tests live under `tests/`: `test_db.py`, `test_diff.py`, `test_filters.py`, `test_notify.py`.
- After behavioural changes to filtering, diffing, DB sync, or formatting, run the full suite and extend tests when adding non-trivial logic.

## 4. Recent durable decisions (2026-03-28)

- **Auth**: Replaced Playwright with plain **httpx**; JWT comes from **GET** `/api/samlauthentication/anonymous` and the **`Jwt` cookie** (former `auth.py` merged into `api.py`).
- **CLI**: **`cleanup --all`** clears the database; `cleanup` requires either a day count or `--all`.
- **UX**: **Court coalescing** for identical time + activity (merged location strings in list/change output).
- **Product**: **Diff-based notifications** with explicit change types: new / gone / bookable.
- **Separation**: **`list` / `check`** are data-only (console); **`notify`** subcommands send Telegram and may sync the DB for `changes`.
