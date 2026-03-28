from src.dedup import DedupStore
from src.api import Slot


def _slot(start: str = "2026-03-29T10:00:00Z") -> Slot:
    return Slot(
        activity_name="Badminton 40 Mins",
        site_id="JOSC",
        site_name="John Orwell",
        location="Court 1",
        date="2026-03-29",
        start_time=start,
        end_time="2026-03-29T10:39:59Z",
    )


def test_new_slot_is_not_seen(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    slot = _slot()
    assert store.is_seen(slot) is False


def test_mark_and_check(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    slot = _slot()
    store.mark_seen([slot])
    assert store.is_seen(slot) is True


def test_different_slots_are_independent(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    slot1 = _slot("2026-03-29T10:00:00Z")
    slot2 = _slot("2026-03-29T11:00:00Z")
    store.mark_seen([slot1])
    assert store.is_seen(slot1) is True
    assert store.is_seen(slot2) is False


def test_persistence(tmp_path):
    path = tmp_path / "notified.json"
    store1 = DedupStore(path)
    slot = _slot()
    store1.mark_seen([slot])

    store2 = DedupStore(path)
    assert store2.is_seen(slot) is True


def test_cleanup_old_entries(tmp_path):
    store = DedupStore(tmp_path / "notified.json")
    old_slot = _slot("2020-01-01T10:00:00Z")
    store.mark_seen([old_slot])
    store.cleanup()
    assert store.is_seen(old_slot) is False
