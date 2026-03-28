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
