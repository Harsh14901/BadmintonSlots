import json
from datetime import datetime, timezone
from pathlib import Path

from src.api import Slot


class DedupStore:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._seen: set[str] = set()
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self._seen = set(data)

    @staticmethod
    def _key(slot: Slot) -> str:
        return f"{slot.site_id}|{slot.location}|{slot.start_time}"

    def is_seen(self, slot: Slot) -> bool:
        return self._key(slot) in self._seen

    def mark_seen(self, slots: list[Slot]) -> None:
        for slot in slots:
            self._seen.add(self._key(slot))
        self._save()

    def cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        to_remove = set()
        for key in self._seen:
            try:
                ts = key.rsplit("|", 1)[1]
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt < now:
                    to_remove.add(key)
            except (ValueError, IndexError):
                to_remove.add(key)
        self._seen -= to_remove
        self._save()

    def _save(self) -> None:
        self._path.write_text(json.dumps(sorted(self._seen)))
