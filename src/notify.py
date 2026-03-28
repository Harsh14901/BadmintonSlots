from datetime import datetime, timezone

import httpx

from src.api import Slot
from src.diff import SlotChange
from src.tz import parse_utc, to_local


CHANGE_EMOJI = {"new": "🟢", "gone": "🔴", "bookable": "🟡"}
CHANGE_LABEL = {"new": "NEW", "gone": "GONE", "bookable": "NOW BOOKABLE"}


def _bookable_suffix(slot: Slot, *, escape_md: bool = False) -> str:
    if not slot.bookable_from:
        return ""
    now = datetime.now(timezone.utc)
    bookable_dt = parse_utc(slot.bookable_from)
    if bookable_dt <= now:
        return ""
    local_bf = to_local(bookable_dt)
    label = local_bf.strftime("%a %d %b %H:%M")
    if escape_md:
        return f" ⏳ _{_escape_markdown(label)}_"
    return f"  ⏳ bookable from {label}"


def format_slot_line(slot: Slot) -> str:
    start_local = to_local(parse_utc(slot.start_time))
    end_local = to_local(parse_utc(slot.end_time))
    start = start_local.strftime("%H:%M")
    end = end_local.strftime("%H:%M")
    suffix = _bookable_suffix(slot)
    return f"    {start}–{end}  {slot.activity_name:<20s} {slot.location}{suffix}"


def format_slot_list(slots: list[Slot]) -> str:
    if not slots:
        return "\n  No matching slots found."

    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        local_start = to_local(parse_utc(slot.start_time))
        local_date = local_start.strftime("%Y-%m-%d")
        key = f"{local_date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    lines: list[str] = []
    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"\n  📅 {day_label} — {site_name}")
        lines.append(f"  {'─' * 70}")
        for s in sorted(grouped[key], key=lambda x: x.start_time):
            lines.append(format_slot_line(s))

    return "\n".join(lines)


def format_slot_list_telegram(slots: list[Slot]) -> str:
    if not slots:
        return ""

    grouped: dict[str, list[Slot]] = {}
    for slot in slots:
        local_start = to_local(parse_utc(slot.start_time))
        local_date = local_start.strftime("%Y-%m-%d")
        key = f"{local_date}|{slot.site_name}"
        grouped.setdefault(key, []).append(slot)

    lines = ["🏸 *Available Badminton Slots\\!*\n"]
    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"📅 *{_escape_markdown(day_label)} — {_escape_markdown(site_name)}*")
        for s in sorted(grouped[key], key=lambda x: x.start_time):
            start_local = to_local(parse_utc(s.start_time))
            end_local = to_local(parse_utc(s.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            activity = _escape_markdown(s.activity_name)
            location = _escape_markdown(s.location)
            suffix = _bookable_suffix(s, escape_md=True)
            lines.append(f"  • {start}–{end} \\| {activity} \\| {location}{suffix}")
        lines.append("")

    return "\n".join(lines)


def format_change_line(change: SlotChange, *, escape_md: bool = False) -> str:
    s = change.slot
    start_local = to_local(parse_utc(s.start_time))
    end_local = to_local(parse_utc(s.end_time))
    start = start_local.strftime("%H:%M")
    end = end_local.strftime("%H:%M")
    emoji = CHANGE_EMOJI[change.change_type]
    label = CHANGE_LABEL[change.change_type]

    if escape_md:
        activity = _escape_markdown(s.activity_name)
        location = _escape_markdown(s.location)
        suffix = _bookable_suffix(s, escape_md=True)
        return f"  {emoji} {label}: {start}–{end} \\| {activity} \\| {location}{suffix}"

    suffix = _bookable_suffix(s)
    return f"    {emoji} {label:<13s} {start}–{end}  {s.activity_name:<20s} {s.location}{suffix}"


def _escape_markdown(text: str) -> str:
    for char in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(char, f"\\{char}")
    return text


def group_changes(changes: list[SlotChange]) -> dict[str, list[SlotChange]]:
    grouped: dict[str, list[SlotChange]] = {}
    for change in changes:
        local_start = to_local(parse_utc(change.slot.start_time))
        local_date = local_start.strftime("%Y-%m-%d")
        key = f"{local_date}|{change.slot.site_name}"
        grouped.setdefault(key, []).append(change)
    return grouped


def format_console(changes: list[SlotChange]) -> str:
    if not changes:
        return "\n  No slot changes detected."

    grouped = group_changes(changes)
    lines: list[str] = []
    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"\n  📅 {day_label} — {site_name}")
        lines.append(f"  {'─' * 70}")
        for c in sorted(grouped[key], key=lambda x: x.slot.start_time):
            lines.append(format_change_line(c))

    return "\n".join(lines)


def format_telegram(changes: list[SlotChange]) -> str:
    if not changes:
        return ""

    grouped = group_changes(changes)
    lines = ["🏸 *Badminton Slot Changes\\!*\n"]
    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        lines.append(f"📅 *{_escape_markdown(day_label)} — {_escape_markdown(site_name)}*")
        for c in sorted(grouped[key], key=lambda x: x.slot.start_time):
            lines.append(format_change_line(c, escape_md=True))
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
