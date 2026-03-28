import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.auth import get_jwt
from src.api import fetch_available_slots
from src.db import SlotDB
from src.diff import compute_changes
from src.filters import matches_rules
from src.notify import format_console, format_telegram, send_telegram


PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "slots.db"


def do_check() -> None:
    config_path = PROJECT_ROOT / "config.json"
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

    now = datetime.now(timezone.utc)
    date_from = now.strftime("%Y-%m-%d")
    date_to = (now + timedelta(days=config["check_days"])).strftime("%Y-%m-%d")

    db = SlotDB(DB_PATH)
    try:
        stored = db.get_slots_in_range(date_from, date_to)
        changes = compute_changes(stored, matching)

        new_count = sum(1 for c in changes if c.change_type == "new")
        gone_count = sum(1 for c in changes if c.change_type == "gone")
        bookable_count = sum(1 for c in changes if c.change_type == "bookable")
        print(f"  Changes: {new_count} new, {gone_count} gone, {bookable_count} now bookable")

        db.sync(matching, changes)

        print("\n🏸 Badminton Slot Changes:")
        print(format_console(changes))

        if not changes:
            return

        if not telegram.get("bot_token") or not telegram.get("chat_id"):
            print("\n⚠️  Telegram not configured — skipping notification")
            return

        message = format_telegram(changes)
        print("\nSending Telegram notification...")
        try:
            send_telegram(message, telegram["bot_token"], telegram["chat_id"])
            print("Done!")
        except Exception as e:
            print(f"⚠️  Telegram send failed: {e}")
    finally:
        db.close()


def do_cleanup(days: int) -> None:
    db = SlotDB(DB_PATH)
    try:
        removed = db.cleanup(days)
        print(f"Removed {removed} slots older than {days} days.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Badminton slot notifier")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Check for slot changes (default)")

    cleanup_p = sub.add_parser("cleanup", help="Remove old slots from database")
    cleanup_p.add_argument("days", type=int, help="Remove slots older than N days")

    args = parser.parse_args()

    if args.command == "cleanup":
        do_cleanup(args.days)
    else:
        do_check()


if __name__ == "__main__":
    main()
