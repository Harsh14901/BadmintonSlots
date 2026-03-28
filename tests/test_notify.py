from src.api import Slot
from src.notify import format_slot_message


def _slot(
    date: str = "2026-03-28",
    start: str = "2026-03-28T10:00:00Z",
    end: str = "2026-03-28T10:39:59Z",
    activity: str = "Badminton 40 Mins",
    site_name: str = "John Orwell",
    location: str = "Court 1",
    bookable_from: str = "",
) -> Slot:
    return Slot(
        activity_name=activity,
        site_id="JOSC",
        site_name=site_name,
        location=location,
        date=date,
        start_time=start,
        end_time=end,
        bookable_from=bookable_from,
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
        _slot(date="2026-03-28", start="2026-03-28T10:00:00Z", end="2026-03-28T10:39:59Z"),
        _slot(date="2026-03-30", start="2026-03-30T11:00:00Z", end="2026-03-30T11:39:59Z"),
    ]
    msg = format_slot_message(slots)
    assert "Saturday 28 Mar" in msg
    assert "Monday 30 Mar" in msg


def test_sorts_slots_within_group():
    slots = [
        _slot(start="2026-03-28T14:00:00Z", end="2026-03-28T14:39:59Z"),
        _slot(start="2026-03-28T10:00:00Z", end="2026-03-28T10:39:59Z"),
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


def test_bst_time_conversion():
    """April 4 is after BST starts. 12:00 UTC = 13:00 BST."""
    slot = _slot(
        date="2026-04-04",
        start="2026-04-04T12:00:00Z",
        end="2026-04-04T12:59:59Z",
    )
    msg = format_slot_message([slot])
    assert "13:00" in msg
    assert "12:00" not in msg


def test_bookable_from_future():
    """Slots with a future bookable_from should show the indicator."""
    slot = _slot(bookable_from="2030-01-01T00:00:00Z")
    msg = format_slot_message([slot])
    assert "⏳" in msg
