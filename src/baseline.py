"""
Pulls 12 months of PJM DOM zone hourly load, computes a rolling same-hour
baseline, and flags intervals where actual load exceeds it by SPIKE_THRESHOLD.

These flagged windows are the synthetic "AI data center training job events"
used as inputs for the pandapower grid simulation.

Usage:
    python src/baseline.py
Output:
    data/spikes.csv  — flagged intervals with actual MW, baseline MW, and ratio
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# Allow running as `python src/baseline.py` from the project root
sys.path.insert(0, str(Path(__file__).parent))
from fetch_load import fetch_load

SPIKE_THRESHOLD = 1.08   # flag when actual / baseline > 8%
ROLLING_WEEKS = 8        # same-hour lookback window
MIN_PERIODS = 4 * 7      # require at least 4 weeks before computing baseline

OUTPUT_DIR = Path(__file__).parent.parent / "data"


def compute_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Add a rolling same-hour-of-day median baseline column to df.

    For each row at hour H, the baseline is the median of all prior rows
    that also occurred at hour H, within the trailing ROLLING_WEEKS weeks.
    """
    df = df.copy()
    df["hour_of_day"] = df["interval_start_utc"].dt.hour

    baselines = []
    for hour, group in df.groupby("hour_of_day", sort=False):
        group = group.sort_values("interval_start_utc")
        # rolling window of ROLLING_WEEKS * 7 same-hour observations
        rolled = (
            group["mw"]
            .rolling(window=ROLLING_WEEKS * 7, min_periods=MIN_PERIODS)
            .median()
            .shift(1)   # exclude current observation from its own baseline
        )
        baselines.append(group.assign(baseline_mw=rolled))

    result = pd.concat(baselines).sort_values("interval_start_utc").reset_index(drop=True)
    return result


def flag_spikes(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows where actual load exceeds baseline by SPIKE_THRESHOLD."""
    df = df.dropna(subset=["baseline_mw"])
    df = df.copy()
    df["ratio"] = df["mw"] / df["baseline_mw"]
    return df[df["ratio"] > SPIKE_THRESHOLD].reset_index(drop=True)


def main() -> None:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=365)

    print(f"Pulling DOM load  {start.date()} → {end.date()} ...")
    df = fetch_load(start.isoformat(), end.isoformat())
    if df.empty:
        print("No data returned — check API key and connection.")
        return

    print(f"  {len(df)} hourly rows fetched  ({df['mw'].min():.0f}–{df['mw'].max():.0f} MW)")

    print("Computing rolling baseline ...")
    df = compute_baseline(df)

    spikes = flag_spikes(df)
    print(f"  {len(spikes)} spike intervals flagged  (threshold: {SPIKE_THRESHOLD:.0%} above baseline)")

    if spikes.empty:
        print("No spikes found — try lowering SPIKE_THRESHOLD.")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "spikes.csv"
    spikes[["interval_start_utc", "mw", "baseline_mw", "ratio"]].to_csv(out_path, index=False)
    print(f"  Saved → {out_path}")

    print("\nTop 5 spikes:")
    print(
        spikes.nlargest(5, "ratio")[["interval_start_utc", "mw", "baseline_mw", "ratio"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
