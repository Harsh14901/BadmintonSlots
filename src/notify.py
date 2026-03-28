from datetime import datetime

import httpx

from src.api import Slot


def _escape_markdown(text: str) -> str:
    for char in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(char, f"\\{char}")
    return text


def format_slot_message(slots: list[Slot]) -> str:
    if not slots:
        return ""

    lines = ["🏸 *Badminton Slots Available\\!*\n"]
    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        key = f"{slot.date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        day_slots = grouped[key]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"📅 *{_escape_markdown(day_label)} — {_escape_markdown(site_name)}*")
        for s in sorted(day_slots, key=lambda x: x.start_time):
            start_dt = datetime.fromisoformat(s.start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(s.end_time.replace("Z", "+00:00"))
            start = start_dt.strftime("%H:%M")
            end = end_dt.strftime("%H:%M")
            activity = _escape_markdown(s.activity_name)
            location = _escape_markdown(s.location)
            lines.append(f"  • {start}–{end} \\| {activity} \\| {location}")
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
