from src.api import Slot
from src.diff import compute_changes


def _slot(
    start: str = "2026-04-01T16:00:00Z",
    site_id: str = "JOSC",
    location: str = "Court 1",
    bookable_from: str = "",
) -> Slot:
    return Slot(
        activity_name="Badminton 40 Mins",
        site_id=site_id,
        site_name="John Orwell",
        location=location,
        date="2026-04-01",
        start_time=start,
        end_time="2026-04-01T16:39:59Z",
        bookable_from=bookable_from,
    )


def _row(
    start: str = "2026-04-01T16:00:00Z",
    status: str = "available",
    bookable_from: str = "",
    notified_bookable: int = 0,
    site_id: str = "JOSC",
    location: str = "Court 1",
) -> dict:
    return {
        "activity_name": "Badminton 40 Mins",
        "site_id": site_id,
        "site_name": "John Orwell",
        "location": location,
        "date": "2026-04-01",
        "start_time": start,
        "end_time": "2026-04-01T16:39:59Z",
        "bookable_from": bookable_from,
        "status": status,
        "notified_bookable": notified_bookable,
    }


def test_new_slot_detected():
    stored = []
    fresh = [_slot()]
    changes = compute_changes(stored, fresh)
    assert len(changes) == 1
    assert changes[0].change_type == "new"


def test_gone_slot_detected():
    stored = [_row()]
    fresh = []
    changes = compute_changes(stored, fresh)
    assert len(changes) == 1
    assert changes[0].change_type == "gone"


def test_unavailable_stored_not_flagged_as_gone():
    stored = [_row(status="unavailable")]
    fresh = []
    changes = compute_changes(stored, fresh)
    assert len(changes) == 0


def test_reappeared_slot_is_new():
    stored = [_row(status="unavailable")]
    fresh = [_slot()]
    changes = compute_changes(stored, fresh)
    assert len(changes) == 1
    assert changes[0].change_type == "new"


def test_no_changes_when_matching():
    stored = [_row()]
    fresh = [_slot()]
    changes = compute_changes(stored, fresh)
    assert len(changes) == 0


def test_bookable_detected():
    """Slot with past bookable_from that hasn't been notified yet."""
    stored = [_row(bookable_from="2020-01-01T00:00:00Z", notified_bookable=0)]
    fresh = [_slot(bookable_from="2020-01-01T00:00:00Z")]
    changes = compute_changes(stored, fresh)
    assert len(changes) == 1
    assert changes[0].change_type == "bookable"


def test_already_notified_bookable_not_repeated():
    stored = [_row(bookable_from="2020-01-01T00:00:00Z", notified_bookable=1)]
    fresh = [_slot(bookable_from="2020-01-01T00:00:00Z")]
    changes = compute_changes(stored, fresh)
    assert len(changes) == 0


def test_future_bookable_not_flagged():
    stored = [_row(bookable_from="2099-01-01T00:00:00Z", notified_bookable=0)]
    fresh = [_slot(bookable_from="2099-01-01T00:00:00Z")]
    changes = compute_changes(stored, fresh)
    assert len(changes) == 0


def test_multiple_changes():
    stored = [
        _row(start="2026-04-01T10:00:00Z", location="Court 1"),
        _row(start="2026-04-01T11:00:00Z", location="Court 1", status="unavailable"),
    ]
    fresh = [
        _slot(start="2026-04-01T11:00:00Z", location="Court 1"),
        _slot(start="2026-04-01T12:00:00Z", location="Court 2"),
    ]
    changes = compute_changes(stored, fresh)
    types = {c.change_type for c in changes}
    assert "gone" in types
    assert "new" in types
    assert len(changes) == 3
