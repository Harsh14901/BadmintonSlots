from datetime import datetime
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")


def parse_utc(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(UK_TZ)
