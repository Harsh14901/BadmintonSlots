from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from src.api import Slot
from src.db import row_to_slot
from src.tz import parse_utc


@dataclass
class SlotChange:
    slot: Slot
    change_type: Literal["new", "gone", "bookable"]


def compute_changes(stored_rows: list, fresh_slots: list[Slot]) -> list[SlotChange]:
    now = datetime.now(timezone.utc)

    stored_by_key: dict[tuple, dict] = {}
    for row in stored_rows:
        key = (row["site_id"], row["location"], row["start_time"])
        stored_by_key[key] = dict(row)

    fresh_by_key: dict[tuple, Slot] = {}
    for slot in fresh_slots:
        key = (slot.site_id, slot.location, slot.start_time)
        fresh_by_key[key] = slot

    changes: list[SlotChange] = []

    for key, row in stored_by_key.items():
        if row["status"] == "available" and key not in fresh_by_key:
            changes.append(SlotChange(slot=row_to_slot(row), change_type="gone"))

    for key, slot in fresh_by_key.items():
        row = stored_by_key.get(key)
        if row is None or row["status"] == "unavailable":
            changes.append(SlotChange(slot=slot, change_type="new"))
        elif not row["notified_bookable"] and slot.bookable_from:
            bookable_dt = parse_utc(slot.bookable_from)
            if bookable_dt <= now:
                changes.append(SlotChange(slot=slot, change_type="bookable"))

    return changes
