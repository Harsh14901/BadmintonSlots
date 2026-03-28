import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.api import Slot
from src.tz import parse_utc


def row_to_slot(row: sqlite3.Row) -> Slot:
    return Slot(
        activity_name=row["activity_name"],
        site_id=row["site_id"],
        site_name=row["site_name"],
        location=row["location"],
        date=row["date"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        bookable_from=row["bookable_from"],
    )


class SlotDB:
    def __init__(self, path: Path | str):
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                site_id TEXT NOT NULL,
                site_name TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                location TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                bookable_from TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'available',
                notified_bookable INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (site_id, location, start_time)
            )
        """)
        self._conn.commit()

    def get_slots_in_range(self, date_from: str, date_to: str) -> list[sqlite3.Row]:
        cursor = self._conn.execute(
            "SELECT * FROM slots WHERE date >= ? AND date <= ?",
            (date_from, date_to),
        )
        return cursor.fetchall()

    def sync(self, fresh_slots: list[Slot], changes: list) -> None:
        now = datetime.now(timezone.utc).isoformat()
        now_dt = datetime.now(timezone.utc)
        with self._conn:
            for slot in fresh_slots:
                already_bookable = 0
                if slot.bookable_from:
                    try:
                        already_bookable = 1 if parse_utc(slot.bookable_from) <= now_dt else 0
                    except ValueError:
                        pass

                self._conn.execute("""
                    INSERT INTO slots
                        (site_id, site_name, activity_name, location, date,
                         start_time, end_time, bookable_from,
                         status, notified_bookable, first_seen_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?, ?)
                    ON CONFLICT(site_id, location, start_time) DO UPDATE SET
                        status = 'available',
                        activity_name = excluded.activity_name,
                        site_name = excluded.site_name,
                        date = excluded.date,
                        end_time = excluded.end_time,
                        bookable_from = excluded.bookable_from,
                        notified_bookable = CASE
                            WHEN slots.status = 'unavailable' THEN excluded.notified_bookable
                            ELSE slots.notified_bookable
                        END,
                        updated_at = excluded.updated_at
                """, (
                    slot.site_id, slot.site_name, slot.activity_name,
                    slot.location, slot.date, slot.start_time, slot.end_time,
                    slot.bookable_from, already_bookable, now, now,
                ))

            for change in changes:
                s = change.slot
                if change.change_type == "gone":
                    self._conn.execute(
                        "UPDATE slots SET status = 'unavailable', updated_at = ?"
                        " WHERE site_id = ? AND location = ? AND start_time = ?",
                        (now, s.site_id, s.location, s.start_time),
                    )
                elif change.change_type == "bookable":
                    self._conn.execute(
                        "UPDATE slots SET notified_bookable = 1, updated_at = ?"
                        " WHERE site_id = ? AND location = ? AND start_time = ?",
                        (now, s.site_id, s.location, s.start_time),
                    )

    def cleanup(self, *, days: int | None = None) -> int:
        if days is None:
            cursor = self._conn.execute("DELETE FROM slots")
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
            cursor = self._conn.execute("DELETE FROM slots WHERE date < ?", (cutoff,))
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
