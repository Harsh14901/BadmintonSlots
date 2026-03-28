from src.api import Slot
from src.diff import SlotChange
from src.notify import (
    _coalesce_locations,
    format_console,
    format_slot_list,
    format_telegram,
)


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


def _change(change_type: str = "new", **kwargs) -> SlotChange:
    return SlotChange(slot=_slot(**kwargs), change_type=change_type)


def test_empty_changes_console():
    output = format_console([])
    assert "No slot changes" in output


def test_empty_changes_telegram():
    assert format_telegram([]) == ""


def test_new_slot_console():
    output = format_console([_change("new")])
    assert "🟢" in output
    assert "NEW" in output
    assert "10:00" in output
    assert "John Orwell" in output


def test_gone_slot_console():
    output = format_console([_change("gone")])
    assert "🔴" in output
    assert "GONE" in output


def test_bookable_slot_console():
    output = format_console([_change("bookable")])
    assert "🟡" in output
    assert "NOW BOOKABLE" in output


def test_groups_by_date_and_site():
    changes = [
        _change("new", date="2026-03-28", start="2026-03-28T10:00:00Z", end="2026-03-28T10:39:59Z"),
        _change("new", date="2026-03-30", start="2026-03-30T11:00:00Z", end="2026-03-30T11:39:59Z"),
    ]
    output = format_console(changes)
    assert "Saturday 28 Mar" in output
    assert "Monday 30 Mar" in output


def test_bst_time_conversion():
    """April 4 is after BST. 12:00 UTC = 13:00 BST."""
    change = _change("new", date="2026-04-04", start="2026-04-04T12:00:00Z", end="2026-04-04T12:59:59Z")
    output = format_console([change])
    assert "13:00" in output
    assert "12:00" not in output


def test_bookable_from_shown_for_new():
    change = _change("new", bookable_from="2099-01-01T00:00:00Z")
    output = format_console([change])
    assert "⏳" in output
    assert "bookable from" in output


def test_telegram_escapes_special():
    change = _change("new", location="Court_1 (special)")
    msg = format_telegram([change])
    assert "Court\\_1" in msg
    assert "\\(special\\)" in msg


def test_coalesce_locations_single():
    assert _coalesce_locations(["Poplar Baths Court 3"]) == "Poplar Baths Court 3"


def test_coalesce_locations_multiple():
    locs = ["Poplar Baths Court 3", "Poplar Baths Court 1", "Poplar Baths Court 4"]
    assert _coalesce_locations(locs) == "Poplar Baths Court 1, 3, 4"


def test_coalesce_locations_different_prefixes():
    locs = ["Court A 1", "Other Court 2"]
    assert _coalesce_locations(locs) == "Court A 1, Other Court 2"


def test_coalesce_slots_in_list():
    slots = [
        _slot(location="John Orwell Court 3"),
        _slot(location="John Orwell Court 1"),
        _slot(location="John Orwell Court 4"),
    ]
    output = format_slot_list(slots)
    assert "Court 1, 3, 4" in output


def test_coalesce_changes_console():
    changes = [
        _change("new", location="John Orwell Court 4"),
        _change("new", location="John Orwell Court 1"),
        _change("new", location="John Orwell Court 3"),
    ]
    output = format_console(changes)
    assert "Court 1, 3, 4" in output
