import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.api import Slot, fetch_available_slots, get_jwt
from src.db import SlotDB
from src.diff import SlotChange, compute_changes
from src.filters import matches_rules
from src.notify import (
    format_console,
    format_slot_list,
    format_slot_list_telegram,
    format_telegram,
    send_telegram,
)


PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "slots.db"


def _load_config() -> dict:
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)
    return json.loads(config_path.read_text())


def _fetch_matching(config: dict) -> list[Slot]:
    rules = config.get("rules", [])

    print("Obtaining JWT...")
    jwt = get_jwt()

    print("Fetching available slots...")
    all_slots = fetch_available_slots(jwt, config)
    print(f"  Found {len(all_slots)} available slots total")

    matching = [s for s in all_slots if matches_rules(s, rules)]
    print(f"  {len(matching)} match configured rules")
    return matching


def _compute_and_sync(config: dict, matching: list[Slot], *, dry_run: bool = False) -> list[SlotChange]:
    now = datetime.now(timezone.utc)
    date_from = now.strftime("%Y-%m-%d")
    date_to = (now + timedelta(days=config["check_days"])).strftime("%Y-%m-%d")

    db = SlotDB(DB_PATH)
    try:
        stored = db.get_slots_in_range(date_from, date_to)
        changes = compute_changes(stored, matching)
        if not dry_run:
            db.sync(matching, changes)
        return changes
    finally:
        db.close()


def _send_telegram(message: str) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        print("\n⚠️  Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars")
        sys.exit(1)

    print("Sending Telegram notification...")
    try:
        send_telegram(message, bot_token, chat_id)
        print("Done!")
    except Exception as e:
        print(f"⚠️  Telegram send failed: {e}")


def do_list() -> None:
    config = _load_config()
    matching = _fetch_matching(config)
    print("\n🏸 Available Badminton Slots:")
    print(format_slot_list(matching))


def do_check(*, dry_run: bool = False) -> None:
    config = _load_config()
    matching = _fetch_matching(config)
    changes = _compute_and_sync(config, matching, dry_run=dry_run)

    new_count = sum(1 for c in changes if c.change_type == "new")
    gone_count = sum(1 for c in changes if c.change_type == "gone")
    bookable_count = sum(1 for c in changes if c.change_type == "bookable")
    print(f"  Changes: {new_count} new, {gone_count} gone, {bookable_count} now bookable")

    print("\n🏸 Badminton Slot Changes:")
    print(format_console(changes))


def do_notify_current() -> None:
    config = _load_config()
    matching = _fetch_matching(config)

    print("\n🏸 Available Badminton Slots:")
    print(format_slot_list(matching))

    message = format_slot_list_telegram(matching)
    if not message:
        print("\nNo slots to send.")
        return
    _send_telegram(message)


def do_notify_changes() -> None:
    config = _load_config()
    matching = _fetch_matching(config)
    changes = _compute_and_sync(config, matching)

    new_count = sum(1 for c in changes if c.change_type == "new")
    gone_count = sum(1 for c in changes if c.change_type == "gone")
    bookable_count = sum(1 for c in changes if c.change_type == "bookable")
    print(f"  Changes: {new_count} new, {gone_count} gone, {bookable_count} now bookable")

    print("\n🏸 Badminton Slot Changes:")
    print(format_console(changes))

    message = format_telegram(changes)
    if not message:
        print("\nNo changes to send.")
        return
    _send_telegram(message)


def do_cleanup(*, days: int | None = None) -> None:
    db = SlotDB(DB_PATH)
    try:
        removed = db.cleanup(days=days)
        if days is None:
            print(f"Removed all {removed} slots.")
        else:
            print(f"Removed {removed} slots older than {days} days.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Badminton slot notifier")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="Fetch and display current available slots")
    check_p = sub.add_parser("check", help="Check for slot changes and update DB (default)")
    check_p.add_argument("--dry-run", action="store_true", help="Show changes without updating the database")

    notify_p = sub.add_parser("notify", help="Send notifications to Telegram")
    notify_sub = notify_p.add_subparsers(dest="notify_command")
    notify_sub.add_parser("current", help="Post current available slots to Telegram")
    notify_sub.add_parser("changes", help="Post slot changes to Telegram")

    cleanup_p = sub.add_parser("cleanup", help="Remove old slots from database")
    cleanup_g = cleanup_p.add_mutually_exclusive_group(required=True)
    cleanup_g.add_argument("days", type=int, nargs="?", default=None, help="Remove slots older than N days")
    cleanup_g.add_argument("--all", action="store_true", help="Remove all slots")

    args = parser.parse_args()

    if args.command == "list":
        do_list()
    elif args.command == "check":
        do_check(dry_run=args.dry_run)
    elif args.command == "notify":
        if args.notify_command == "current":
            do_notify_current()
        elif args.notify_command == "changes":
            do_notify_changes()
        else:
            notify_p.print_help()
    elif args.command == "cleanup":
        do_cleanup(days=None if args.all else args.days)
    else:
        do_check()


if __name__ == "__main__":
    main()
