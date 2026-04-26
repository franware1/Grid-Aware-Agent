"""
Fetches PJM DOM zone hourly metered load from GridStatus API.
DOM = Dominion Energy (Northern Virginia / data center corridor).
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.gridstatus.io/v1/datasets/pjm_load_metered_hourly/query"
ZONE = "DOM"


def _get_headers() -> dict:
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        raise EnvironmentError("GRIDSTATUS_API_KEY not set — copy .env.example to .env and add your key")
    return {"X-API-Key": key}


def fetch_load(start: str, end: str, page_size: int = 50000) -> pd.DataFrame:
    """Return a DataFrame of DOM zone aggregate hourly load between start and end (ISO-8601).

    Paginates automatically. Uses load_area=DOM for the zone-level aggregate.
    """
    all_rows = []
    page = 1
    while True:
        params = {
            "start_time": start,
            "end_time": end,
            "filter_column": "load_area",
            "filter_value": ZONE,
            "columns": "interval_start_utc,mw",
            "order": "asc",
            "page": page,
            "page_size": page_size,
        }
        resp = requests.get(BASE_URL, headers=_get_headers(), params=params, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("data", [])
        all_rows.extend(rows)
        if not body.get("meta", {}).get("hasNextPage"):
            break
        page += 1

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["interval_start_utc"] = pd.to_datetime(df["interval_start_utc"], utc=True)
    df = df.sort_values("interval_start_utc").reset_index(drop=True)
    return df


def test_connection() -> None:
    """Quick smoke test — fetches one week of data and prints summary."""
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=7)
    print(f"Fetching DOM load  {start.date()} → {end.date()} ...")
    df = fetch_load(start.isoformat(), end.isoformat())
    if df.empty:
        print("Connection OK but no rows returned.")
        return
    print(f"Rows returned : {len(df)}")
    print(f"Load range    : {df['mw'].min():.0f} – {df['mw'].max():.0f} MW")
    print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    test_connection()
