from datetime import datetime, timezone

import httpx

from src.api import Slot
from src.tz import parse_utc, to_local


def _escape_markdown(text: str) -> str:
    for char in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(char, f"\\{char}")
    return text


def format_slot_message(slots: list[Slot]) -> str:
    if not slots:
        return ""

    now = datetime.now(timezone.utc)
    lines = ["🏸 *Badminton Slots Available\\!*\n"]
    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        local_start = to_local(parse_utc(slot.start_time))
        local_date = local_start.strftime("%Y-%m-%d")
        key = f"{local_date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        day_slots = grouped[key]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"📅 *{_escape_markdown(day_label)} — {_escape_markdown(site_name)}*")
        for s in sorted(day_slots, key=lambda x: x.start_time):
            start_local = to_local(parse_utc(s.start_time))
            end_local = to_local(parse_utc(s.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            activity = _escape_markdown(s.activity_name)
            location = _escape_markdown(s.location)
            line = f"  • {start}–{end} \\| {activity} \\| {location}"
            if s.bookable_from:
                bookable_dt = parse_utc(s.bookable_from)
                if bookable_dt > now:
                    bookable_local = to_local(bookable_dt)
                    line += f" ⏳ _{_escape_markdown(bookable_local.strftime('%a %d %b %H:%M'))}_"
            lines.append(line)
        lines.append("")

    return "\n".join(lines)


def send_telegram(message: str, bot_token: str, chat_id: str) -> None:
    if not message:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = [message[i : i + 4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        resp = httpx.post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "MarkdownV2",
            },
            timeout=10,
        )
        resp.raise_for_status()
