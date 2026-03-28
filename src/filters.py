from datetime import datetime

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
