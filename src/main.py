import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.auth import get_jwt
from src.api import Slot, fetch_available_slots
from src.filters import matches_rules
from src.dedup import DedupStore
from src.notify import format_slot_message, send_telegram
from src.tz import parse_utc, to_local


def print_slots(slots: list[Slot]) -> None:
    if not slots:
        print("\n  No matching slots found.")
        return

    now = datetime.now(timezone.utc)
    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        local_start = to_local(parse_utc(slot.start_time))
        local_date = local_start.strftime("%Y-%m-%d")
        key = f"{local_date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        print(f"\n  📅 {day_label} — {site_name}")
        print(f"  {'─' * 60}")
        for s in sorted(grouped[key], key=lambda x: x.start_time):
            start_local = to_local(parse_utc(s.start_time))
            end_local = to_local(parse_utc(s.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            line = f"    {start}–{end}  {s.activity_name:<20s} {s.location}"
            if s.bookable_from:
                bookable_dt = parse_utc(s.bookable_from)
                if bookable_dt > now:
                    bookable_local = to_local(bookable_dt)
                    line += f"  ⏳ bookable from {bookable_local.strftime('%a %d %b %H:%M')}"
            print(line)


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

    print("\n🏸 Available Badminton Slots:")
    print_slots(new_slots)

    if not new_slots:
        return

    if not telegram.get("bot_token"):
        print("\n⚠️  Telegram bot_token not configured — skipping notification")
        return

    message = format_slot_message(new_slots)
    print("\nSending Telegram notification...")
    send_telegram(message, telegram["bot_token"], telegram["chat_id"])
    store.mark_seen(new_slots)
    print("Done!")


if __name__ == "__main__":
    main()
