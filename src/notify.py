from datetime import datetime

import httpx

from src.api import Slot


def format_slot_message(slots: list[Slot]) -> str:
    if not slots:
        return ""

    lines = ["🏸 *Badminton Slots Available!*\n"]
    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        key = f"{slot.date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        day_slots = grouped[key]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"📅 *{day_label} — {site_name}*")
        for s in sorted(day_slots, key=lambda x: x.start_time):
            start = s.start_time[11:16]
            end = s.end_time[11:16]
            lines.append(f"  • {start}–{end} | {s.activity_name} | {s.location}")
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
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        resp.raise_for_status()
