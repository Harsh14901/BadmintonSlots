import re
from datetime import datetime, timezone
from itertools import groupby

import httpx

from src.api import Slot
from src.diff import SlotChange
from src.tz import parse_utc, to_local


CHANGE_EMOJI = {"new": "🟢", "gone": "🔴", "bookable": "🟡"}
CHANGE_LABEL = {"new": "NEW", "gone": "GONE", "bookable": "NOW BOOKABLE"}

_COURT_RE = re.compile(r"^(.+?Court\s*)\d+$")


def _coalesce_locations(locations: list[str]) -> str:
    if len(locations) == 1:
        return locations[0]
    m = _COURT_RE.match(locations[0])
    if not m:
        return ", ".join(locations)
    prefix = m.group(1)
    numbers: list[str] = []
    for loc in locations:
        m = _COURT_RE.match(loc)
        if m and m.group(1) == prefix:
            numbers.append(loc[len(prefix):])
        else:
            return ", ".join(locations)
    numbers.sort(key=lambda n: int(n))
    return f"{prefix}{', '.join(numbers)}"


def _bookable_label(bookable_from: str) -> str:
    if not bookable_from:
        return ""
    now = datetime.now(timezone.utc)
    try:
        bookable_dt = parse_utc(bookable_from)
    except ValueError:
        return ""
    if bookable_dt <= now:
        return ""
    return to_local(bookable_dt).strftime("%a %d %b %H:%M")


def _group_bookable_label(slots: list[Slot]) -> str:
    """Returns common bookable label if every slot in the group shares the same one, else empty."""
    labels = {_bookable_label(s.bookable_from) for s in slots}
    if len(labels) == 1 and "" not in labels:
        return labels.pop()
    return ""


def _slot_sort_key(slot: Slot) -> tuple:
    return (slot.start_time, slot.end_time, slot.activity_name)


def _coalesce_slots(slots: list[Slot]) -> list[tuple[Slot, str]]:
    """Groups slots sharing the same time+activity, returns (representative_slot, merged_location)."""
    sorted_slots = sorted(slots, key=_slot_sort_key)
    result: list[tuple[Slot, str]] = []
    for _, group in groupby(sorted_slots, key=_slot_sort_key):
        group_list = list(group)
        locations = [s.location for s in group_list]
        merged = _coalesce_locations(locations)
        result.append((group_list[0], merged))
    return result


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
        group_slots = grouped[key]
        group_bf = _group_bookable_label(group_slots)
        header = f"\n  📅 {day_label} — {site_name}"
        if group_bf:
            header += f" (⏳ bookable from {group_bf})"
        lines.append(header)
        lines.append(f"  {'─' * 70}")
        for slot, location in _coalesce_slots(group_slots):
            start_local = to_local(parse_utc(slot.start_time))
            end_local = to_local(parse_utc(slot.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            suffix = ""
            if not group_bf:
                label = _bookable_label(slot.bookable_from)
                if label:
                    suffix = f"  ⏳ bookable from {label}"
            lines.append(f"    {start}–{end}  {slot.activity_name:<20s} {location}{suffix}")

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
        group_slots = grouped[key]
        group_bf = _group_bookable_label(group_slots)
        header = f"📅 *{_escape_markdown(day_label)} — {_escape_markdown(site_name)}"
        if group_bf:
            header += f" \\(⏳ bookable from {_escape_markdown(group_bf)}\\)"
        header += "*"
        lines.append(header)
        for slot, location in _coalesce_slots(group_slots):
            start_local = to_local(parse_utc(slot.start_time))
            end_local = to_local(parse_utc(slot.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            activity = _escape_markdown(slot.activity_name)
            loc_esc = _escape_markdown(location)
            suffix = ""
            if not group_bf:
                label = _bookable_label(slot.bookable_from)
                if label:
                    suffix = f" ⏳ _{_escape_markdown(label)}_"
            lines.append(f"  • {start}–{end} \\| {activity} \\| {loc_esc}{suffix}")
        lines.append("")

    return "\n".join(lines)


def _change_sort_key(change: SlotChange) -> tuple:
    s = change.slot
    return (s.start_time, s.end_time, s.activity_name, change.change_type)


def _coalesce_changes(changes: list[SlotChange]) -> list[tuple[SlotChange, str]]:
    sorted_changes = sorted(changes, key=_change_sort_key)
    result: list[tuple[SlotChange, str]] = []
    for _, group in groupby(sorted_changes, key=_change_sort_key):
        group_list = list(group)
        locations = [c.slot.location for c in group_list]
        merged = _coalesce_locations(locations)
        result.append((group_list[0], merged))
    return result


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
        group_slots = [c.slot for c in grouped[key]]
        group_bf = _group_bookable_label(group_slots)
        header = f"\n  📅 {day_label} — {site_name}"
        if group_bf:
            header += f" (⏳ bookable from {group_bf})"
        lines.append(header)
        lines.append(f"  {'─' * 70}")
        for change, location in _coalesce_changes(grouped[key]):
            s = change.slot
            start_local = to_local(parse_utc(s.start_time))
            end_local = to_local(parse_utc(s.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            emoji = CHANGE_EMOJI[change.change_type]
            label = CHANGE_LABEL[change.change_type]
            suffix = ""
            if not group_bf:
                bf_label = _bookable_label(s.bookable_from)
                if bf_label:
                    suffix = f"  ⏳ bookable from {bf_label}"
            lines.append(f"    {emoji} {label:<13s} {start}–{end}  {s.activity_name:<20s} {location}{suffix}")

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
        group_slots = [c.slot for c in grouped[key]]
        group_bf = _group_bookable_label(group_slots)
        header = f"📅 *{_escape_markdown(day_label)} — {_escape_markdown(site_name)}"
        if group_bf:
            header += f" \\(⏳ bookable from {_escape_markdown(group_bf)}\\)"
        header += "*"
        lines.append(header)
        for change, location in _coalesce_changes(grouped[key]):
            s = change.slot
            start_local = to_local(parse_utc(s.start_time))
            end_local = to_local(parse_utc(s.end_time))
            start = start_local.strftime("%H:%M")
            end = end_local.strftime("%H:%M")
            emoji = CHANGE_EMOJI[change.change_type]
            label = CHANGE_LABEL[change.change_type]
            activity = _escape_markdown(s.activity_name)
            loc_esc = _escape_markdown(location)
            suffix = ""
            if not group_bf:
                bf_label = _bookable_label(s.bookable_from)
                if bf_label:
                    suffix = f" ⏳ _{_escape_markdown(bf_label)}_"
            lines.append(f"  {emoji} {label}: {start}–{end} \\| {activity} \\| {loc_esc}{suffix}")
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
