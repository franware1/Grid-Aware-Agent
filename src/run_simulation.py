"""
Integration bridge: real GridStatus spike data → pandapower simulation.

Loads data/spikes.csv (produced by baseline.py), converts each flagged
interval into a LOAD_SPIKE event scaled to the simulator's 3-bus grid,
runs the EventScheduler + power flow, and prints per-step agent actions.
Targets the DC_NoMa flexible load on Francisco's Pepco DC grid model.

Usage:
    python src/run_simulation.py [--steps N] [--top-spikes]

    --steps N       Run only the first N spike intervals (default: all)
    --top-spikes    Sort by ratio descending (worst spikes first)
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is on the path so simulator.* imports resolve
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from simulation import SimulationEnvironment
from simulator.events import EventScheduler, GridEvent, EventType

# The simulator's DC_NoMa FlexibleLoad has baseline_mw=110.
# DOM zone baseline is ~13,000 MW. We scale spike deltas proportionally.
SIMULATOR_DC_BASELINE_MW = 110.0
DOM_ZONE_BASELINE_MW     = 13_000.0
SCALE = SIMULATOR_DC_BASELINE_MW / DOM_ZONE_BASELINE_MW


def load_spikes(top_spikes: bool = False, steps: int = None) -> pd.DataFrame:
    path = ROOT / "data" / "spikes.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run `python src/baseline.py` first"
        )
    df = pd.read_csv(path, parse_dates=["interval_start_utc"])
    if top_spikes:
        df = df.sort_values("ratio", ascending=False)
    if steps is not None:
        df = df.head(steps)
    return df.reset_index(drop=True)


def run(steps: int = None, top_spikes: bool = False) -> list:
    """Run the simulation and return a list of per-step result dicts."""
    spikes = load_spikes(top_spikes=top_spikes, steps=steps)
    print(f"Loaded {len(spikes)} spike intervals from data/spikes.csv")

    env = SimulationEnvironment(grid_name="Pepco DC — Washington DC")
    env.build_grid()
    env.initialize()
    scheduler = EventScheduler(env.grid)

    print(f"\nRunning {len(spikes)} simulation steps...\n{'='*60}")

    records = []
    for i, row in spikes.iterrows():
        ts        = row["interval_start_utc"]
        delta_mw  = row["mw"] - row["baseline_mw"]
        scaled_mw = delta_mw * SCALE
        ratio     = row["ratio"]

        event = GridEvent(
            name=f"spike_{i}",
            event_type=EventType.LOAD_SPIKE,
            target="DC_NoMa",
            scheduled_at=float(i),
            duration_steps=1,
            params={"delta_mw": scaled_mw},
        )
        scheduler.schedule(event)
        scheduler.tick(timestep=float(i))

        result  = env.step(apply_agent=True)
        pf      = result.get("pf_report") or {}
        summary = pf.get("summary", {})
        agent   = result.get("agent_result") or {}
        actions = [a["action"] for a in agent.get("actions", [])]

        rec = {
            "timestamp":        ts,
            "ratio":            ratio,
            "real_delta_mw":    delta_mw,
            "actual_mw":        row["mw"],
            "baseline_mw":      row["baseline_mw"],
            "line_loading_pct": summary.get("max_line_loading_pct", 0),
            "reserve_mw":       summary.get("reserve_margin_mw", 0),
            "agent_action":     ", ".join(actions),
            "converged":        result.get("converged", False),
            "n_violations":     pf.get("n_violations", 0),
        }
        records.append(rec)

        print(
            f"[{ts}]  ratio={ratio:.2f}x  Δ={delta_mw:+.0f}MW  "
            f"reserve={rec['reserve_mw']:.0f}MW  line={rec['line_loading_pct']:.0f}%  "
            f"agent={actions}"
        )

    print(f"\n{'='*60}")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--top-spikes", action="store_true")
    args = parser.parse_args()
    run(steps=args.steps, top_spikes=args.top_spikes)
