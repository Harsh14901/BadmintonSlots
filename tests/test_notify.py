from src.api import Slot
from src.notify import format_slot_message


def _slot(
    date: str = "2026-03-29",
    start: str = "2026-03-29T10:00:00Z",
    end: str = "2026-03-29T10:39:59Z",
    activity: str = "Badminton 40 Mins",
    site_name: str = "John Orwell",
    location: str = "Court 1",
) -> Slot:
    return Slot(
        activity_name=activity,
        site_id="JOSC",
        site_name=site_name,
        location=location,
        date=date,
        start_time=start,
        end_time=end,
    )


def test_empty_list_returns_empty():
    assert format_slot_message([]) == ""


def test_single_slot_format():
    msg = format_slot_message([_slot()])
    assert "Badminton 40 Mins" in msg
    assert "10:00" in msg
    assert "John Orwell" in msg


def test_groups_by_date_and_site():
    slots = [
        _slot(date="2026-03-29", start="2026-03-29T10:00:00Z", end="2026-03-29T10:39:59Z"),
        _slot(date="2026-03-30", start="2026-03-30T11:00:00Z", end="2026-03-30T11:39:59Z"),
    ]
    msg = format_slot_message(slots)
    assert "Sunday 29 Mar" in msg
    assert "Monday 30 Mar" in msg


def test_sorts_slots_within_group():
    slots = [
        _slot(start="2026-03-29T14:00:00Z", end="2026-03-29T14:39:59Z"),
        _slot(start="2026-03-29T10:00:00Z", end="2026-03-29T10:39:59Z"),
    ]
    msg = format_slot_message(slots)
    pos_10 = msg.index("10:00")
    pos_14 = msg.index("14:00")
    assert pos_10 < pos_14


def test_escapes_special_characters():
    slot = _slot(location="Court_1 (special)")
    msg = format_slot_message([slot])
    assert "Court\\_1" in msg
    assert "\\(special\\)" in msg
