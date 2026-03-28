import re
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import groupby

import httpx

from src.api import Slot
from src.diff import SlotChange
from src.tz import parse_utc, to_local


CHANGE_EMOJI = {"new": "🟢", "gone": "🔴", "bookable": "🟡"}
CHANGE_LABEL = {"new": "NEW", "gone": "GONE", "bookable": "NOW BOOKABLE"}

_COURT_RE = re.compile(r"^(.+?Court\s*)\d+$")


def _escape_markdown(text: str) -> str:
    for char in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(char, f"\\{char}")
    return text


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


def _group_bookable_label(rows: list["_RenderRow"]) -> str:
    labels = {_bookable_label(r.slot.bookable_from) for r in rows}
    if len(labels) == 1 and "" not in labels:
        return labels.pop()
    return ""


# ── Unified rendering pipeline ──────────────────────────────────────


@dataclass
class _RenderRow:
    slot: Slot
    location: str
    change_type: str


def _slots_to_rows(slots: list[Slot]) -> list[_RenderRow]:
    return [_RenderRow(slot=s, location=s.location, change_type="") for s in slots]


def _changes_to_rows(changes: list[SlotChange]) -> list[_RenderRow]:
    return [_RenderRow(slot=c.slot, location=c.slot.location, change_type=c.change_type) for c in changes]


def _coalesce_rows(rows: list[_RenderRow]) -> list[_RenderRow]:
    key_fn = lambda r: (r.slot.start_time, r.slot.end_time, r.slot.activity_name, r.change_type)
    sorted_rows = sorted(rows, key=key_fn)
    result: list[_RenderRow] = []
    for _, group in groupby(sorted_rows, key=key_fn):
        group_list = list(group)
        location = _coalesce_locations([r.location for r in group_list])
        result.append(_RenderRow(
            slot=group_list[0].slot, location=location, change_type=group_list[0].change_type,
        ))
    return result


def _render(
    rows: list[_RenderRow],
    *,
    telegram: bool,
    title: str,
    empty_msg: str,
) -> str:
    if not rows:
        return empty_msg

    grouped: dict[str, list[_RenderRow]] = {}
    for row in rows:
        local_start = to_local(parse_utc(row.slot.start_time))
        local_date = local_start.strftime("%Y-%m-%d")
        key = f"{local_date}|{row.slot.site_name}"
        grouped.setdefault(key, []).append(row)

    esc = _escape_markdown if telegram else lambda x: x
    lines: list[str] = [title] if title else []

    for key in sorted(grouped.keys()):
        date_str, site_name = key.split("|", 1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_label = dt.strftime("%A %d %b")
        group_rows = _coalesce_rows(grouped[key])
        group_bf = _group_bookable_label(group_rows)

        if telegram:
            header = f"📅 *{esc(day_label)} — {esc(site_name)}"
            if group_bf:
                header += f" \\(⏳ bookable from {esc(group_bf)}\\)"
            header += "*"
        else:
            header = f"\n  📅 {day_label} — {site_name}"
            if group_bf:
                header += f" (⏳ bookable from {group_bf})"

        lines.append(header)
        if not telegram:
            lines.append(f"  {'─' * 70}")

        for row in group_rows:
            start = to_local(parse_utc(row.slot.start_time)).strftime("%H:%M")
            end = to_local(parse_utc(row.slot.end_time)).strftime("%H:%M")

            bf_suffix = ""
            if not group_bf:
                label = _bookable_label(row.slot.bookable_from)
                if label:
                    bf_suffix = f" ⏳ _{esc(label)}_" if telegram else f"  ⏳ bookable from {label}"

            if telegram:
                activity = esc(row.slot.activity_name)
                loc = esc(row.location)
                if row.change_type:
                    emoji = CHANGE_EMOJI[row.change_type]
                    clabel = CHANGE_LABEL[row.change_type]
                    lines.append(f"  {emoji} {clabel}: {start}–{end} \\| {activity} \\| {loc}{bf_suffix}")
                else:
                    lines.append(f"  • {start}–{end} \\| {activity} \\| {loc}{bf_suffix}")
            else:
                if row.change_type:
                    emoji = CHANGE_EMOJI[row.change_type]
                    clabel = CHANGE_LABEL[row.change_type]
                    lines.append(
                        f"    {emoji} {clabel:<13s} {start}–{end}  "
                        f"{row.slot.activity_name:<20s} {row.location}{bf_suffix}"
                    )
                else:
                    lines.append(
                        f"    {start}–{end}  {row.slot.activity_name:<20s} {row.location}{bf_suffix}"
                    )

        if telegram:
            lines.append("")

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


def format_slot_list(slots: list[Slot]) -> str:
    return _render(_slots_to_rows(slots), telegram=False, title="", empty_msg="\n  No matching slots found.")


def format_slot_list_telegram(slots: list[Slot]) -> str:
    return _render(
        _slots_to_rows(slots),
        telegram=True,
        title="🏸 *Available Badminton Slots\\!*\n",
        empty_msg="",
    )


def format_console(changes: list[SlotChange]) -> str:
    return _render(
        _changes_to_rows(changes), telegram=False, title="", empty_msg="\n  No slot changes detected.",
    )


def format_telegram(changes: list[SlotChange]) -> str:
    return _render(
        _changes_to_rows(changes),
        telegram=True,
        title="🏸 *Badminton Slot Changes\\!*\n",
        empty_msg="",
    )


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
