from src.api import Slot
from src.db import SlotDB, row_to_slot
from src.diff import SlotChange


def _slot(
    start: str = "2026-04-01T16:00:00Z",
    location: str = "Court 1",
    bookable_from: str = "",
) -> Slot:
    return Slot(
        activity_name="Badminton 40 Mins",
        site_id="JOSC",
        site_name="John Orwell",
        location=location,
        date="2026-04-01",
        start_time=start,
        end_time="2026-04-01T16:39:59Z",
        bookable_from=bookable_from,
    )


def test_sync_inserts_new_slots(tmp_path):
    db = SlotDB(tmp_path / "test.db")
    slot = _slot()
    changes = [SlotChange(slot=slot, change_type="new")]
    db.sync([slot], changes)

    rows = db.get_slots_in_range("2026-04-01", "2026-04-01")
    assert len(rows) == 1
    assert rows[0]["status"] == "available"
    db.close()


def test_sync_marks_gone(tmp_path):
    db = SlotDB(tmp_path / "test.db")
    slot = _slot()
    db.sync([slot], [SlotChange(slot=slot, change_type="new")])

    gone_change = SlotChange(slot=slot, change_type="gone")
    db.sync([], [gone_change])

    rows = db.get_slots_in_range("2026-04-01", "2026-04-01")
    assert len(rows) == 1
    assert rows[0]["status"] == "unavailable"
    db.close()


def test_sync_marks_bookable(tmp_path):
    db = SlotDB(tmp_path / "test.db")
    slot = _slot(bookable_from="2020-01-01T00:00:00Z")
    db.sync([slot], [SlotChange(slot=slot, change_type="new")])

    db.sync([slot], [SlotChange(slot=slot, change_type="bookable")])

    rows = db.get_slots_in_range("2026-04-01", "2026-04-01")
    assert rows[0]["notified_bookable"] == 1
    db.close()


def test_reappeared_slot_resets_notified_bookable(tmp_path):
    db = SlotDB(tmp_path / "test.db")
    slot = _slot(bookable_from="2099-01-01T00:00:00Z")

    db.sync([slot], [SlotChange(slot=slot, change_type="new")])
    rows = db.get_slots_in_range("2026-04-01", "2026-04-01")
    assert rows[0]["notified_bookable"] == 0

    db.sync([], [SlotChange(slot=slot, change_type="gone")])
    db.sync([slot], [SlotChange(slot=slot, change_type="new")])

    rows = db.get_slots_in_range("2026-04-01", "2026-04-01")
    assert rows[0]["status"] == "available"
    assert rows[0]["notified_bookable"] == 0
    db.close()


def test_cleanup(tmp_path):
    db = SlotDB(tmp_path / "test.db")
    old_slot = Slot(
        activity_name="Badminton 40 Mins",
        site_id="JOSC",
        site_name="John Orwell",
        location="Court 1",
        date="2020-01-01",
        start_time="2020-01-01T10:00:00Z",
        end_time="2020-01-01T10:39:59Z",
        bookable_from="",
    )
    db.sync([old_slot], [SlotChange(slot=old_slot, change_type="new")])
    assert len(db.get_slots_in_range("2020-01-01", "2020-01-01")) == 1

    removed = db.cleanup(days=1)
    assert removed == 1
    assert len(db.get_slots_in_range("2020-01-01", "2020-01-01")) == 0
    db.close()


def test_row_to_slot(tmp_path):
    db = SlotDB(tmp_path / "test.db")
    original = _slot(bookable_from="2026-03-29T00:00:00Z")
    db.sync([original], [SlotChange(slot=original, change_type="new")])

    rows = db.get_slots_in_range("2026-04-01", "2026-04-01")
    restored = row_to_slot(rows[0])
    assert restored.site_id == original.site_id
    assert restored.start_time == original.start_time
    assert restored.bookable_from == original.bookable_from
    db.close()
