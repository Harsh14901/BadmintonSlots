from datetime import datetime, timedelta

from src.filters import matches_rules
from src.api import Slot


def _slot(day_name: str, hour: int, minute: int = 0, activity_name: str = "Badminton 40 Mins", site_id: str = "JOSC") -> Slot:
    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    target = day_map[day_name]
    today = datetime.now()
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    d = today.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    date_str = d.strftime("%Y-%m-%d")
    start = f"{date_str}T{hour:02d}:{minute:02d}:00Z"
    end = f"{date_str}T{hour:02d}:{minute + 39}:59Z"
    return Slot(
        activity_name=activity_name,
        site_id=site_id,
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
    slot_josc = _slot("mon", 10)
    assert matches_rules(slot_josc, rules) is False


def test_activity_filter_40():
    rules = [{"days": ["mon"], "start": "09:00", "end": "22:00", "activity": "40"}]
    slot = _slot("mon", 10)
    assert matches_rules(slot, rules) is True


def test_activity_filter_60_no_match():
    rules = [{"days": ["mon"], "start": "09:00", "end": "22:00", "activity": "60"}]
    slot = _slot("mon", 10)
    assert matches_rules(slot, rules) is False
