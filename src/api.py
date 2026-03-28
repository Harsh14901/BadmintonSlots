from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

import httpx

from src.constants import BASE_URL


@dataclass(frozen=True)
class Slot:
    activity_name: str
    site_id: str
    site_name: str
    location: str
    date: str
    start_time: str
    end_time: str


def fetch_available_slots(jwt: str, config: dict) -> list[Slot]:
    activity_ids = ",".join(config["activities"].keys())
    site_ids = ",".join(config["sites"].keys())
    date_from = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00.000Z")

    url = f"{BASE_URL}/api/availability/V2/sessions"
    params = {
        "webBookableOnly": "true",
        "siteIds": site_ids,
        "activityIds": activity_ids,
        "dateFrom": date_from,
    }
    headers = {
        "accept": "application/json",
        "x-use-sso": "1",
    }
    cookies = {"Jwt": jwt}

    resp = httpx.get(url, params=params, headers=headers, cookies=cookies, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    cutoff_date = (datetime.now(timezone.utc) + timedelta(days=config["check_days"])).strftime("%Y-%m-%d")

    slots: list[Slot] = []
    for activity in data:
        if activity["date"] > cutoff_date:
            continue
        for loc in activity["locations"]:
            for slot in loc["slots"]:
                if slot["status"] != "Available":
                    continue
                site_name = config["sites"].get(activity["siteId"], activity["siteId"])
                slots.append(Slot(
                    activity_name=activity["name"],
                    site_id=activity["siteId"],
                    site_name=site_name,
                    location=loc["locationNameToDisplay"],
                    date=activity["date"],
                    start_time=slot["startTime"],
                    end_time=slot["endTime"],
                ))
    return slots
