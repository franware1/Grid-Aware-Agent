"""
src/llm_agent.py
Two-Brain Agent — drop-in alongside run_simulation.py

Wraps SimulationEnvironment.step() with Brain 1 (risk scorer)
and Brain 2 (LLM reasoning). Their GridOptimizationAgent keeps
running unchanged. Ours layers on top.

Usage:
    from llm_agent import run_with_llm_agent
    records = run_with_llm_agent(steps=20, top_spikes=True)

Or run directly:
    python src/llm_agent.py --steps 20
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from simulator.simulation import SimulationEnvironment
from simulator.events import EventScheduler, GridEvent, EventType
from simulator.brain1 import score as brain1_score
from simulator.brain2 import run as brain2_run

# Same scaling as run_simulation.py — keep consistent
SIMULATOR_DC_BASELINE_MW = 110.0
DOM_ZONE_BASELINE_MW     = 13_000.0
SCALE = SIMULATOR_DC_BASELINE_MW / DOM_ZONE_BASELINE_MW

# Only call Brain 2 (LLM) when Brain 1 says risk is elevated.
# Keeps API calls focused on real events, not every quiet timestep.
BRAIN2_THRESHOLD = 0.55


def _load_spikes(top_spikes: bool, steps: int | None) -> pd.DataFrame:
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


def _print_step(i: int, ts, ratio: float, risk: dict, b2: dict | None):
    """Console output for each step."""
    risk_str = f"risk={risk['overall_risk']:.2f} threat={risk['top_threat']}"
    if b2:
        print(
            f"[{ts}]  ratio={ratio:.2f}x  {risk_str}\n"
            f"  Brain2 → {b2['action']} | {b2['confidence']} confidence\n"
            f"  Threat : {b2['threat_summary']}\n"
            f"  Reason : {b2['reasoning']}\n"
        )
    else:
        print(f"[{ts}]  ratio={ratio:.2f}x  {risk_str}  (below threshold — no LLM call)")


def run_with_llm_agent(
    steps: int | None = None,
    top_spikes: bool = False,
    verbose: bool = True,
) -> list[dict]:
    """
    Main runner. Mirrors run_simulation.py structure so dashboard.py
    can call either interchangeably.

    Returns list of per-step record dicts.
    """
    spikes = _load_spikes(top_spikes=top_spikes, steps=steps)
    print(f"Loaded {len(spikes)} spike intervals")

    env = SimulationEnvironment(grid_name="Pepco DC — Washington DC")
    env.build_grid()
    env.initialize()
    scheduler = EventScheduler(env.grid)

    print(f"\nRunning {len(spikes)} steps with two-brain agent...\n{'='*60}")

    records = []
    brain2_calls = 0

    for i, row in spikes.iterrows():
        ts        = row["interval_start_utc"]
        delta_mw  = row["mw"] - row["baseline_mw"]
        scaled_mw = delta_mw * SCALE
        ratio     = row["ratio"]

        # Inject spike event — same as run_simulation.py
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

        # Their simulation step (runs their rule-based agent)
        result     = env.step(apply_agent=True)
        pf_report  = result.get("pf_report") or {}
        their_action = result.get("agent_result") or {}

        # ── Brain 1: score risk ───────────────────────────────────────────────
        risk = brain1_score(pf_report, result)

        # ── Brain 2: reason if risk is elevated ──────────────────────────────
        b2_result = None
        if risk["action_needed"] and risk["overall_risk"] >= BRAIN2_THRESHOLD:
            b2_result = brain2_run(
                risk=risk,
                their_action=their_action,
                time_step=i,
            )
            brain2_calls += 1

        if verbose:
            _print_step(i, ts, ratio, risk, b2_result)

        # ── Build record ──────────────────────────────────────────────────────
        summary = pf_report.get("summary", {})
        their_acts = [a["action"] for a in their_action.get("actions", [])]

        rec = {
            # Spike data
            "timestamp":       ts,
            "ratio":           ratio,
            "real_delta_mw":   delta_mw,
            "actual_mw":       row["mw"],
            "baseline_mw":     row["baseline_mw"],
            # Their agent
            "rule_agent_action": ", ".join(their_acts),
            "converged":         result.get("converged", False),
            "n_violations":      pf_report.get("n_violations", 0),
            # Grid state
            "line_loading_pct":  summary.get("max_line_loading_pct", 0),
            "reserve_mw":        summary.get("reserve_margin_mw", 0),
            # Brain 1
            "brain1_risk":       risk["overall_risk"],
            "brain1_threat":     risk["top_threat"],
            "brain1_action_needed": risk["action_needed"],
            # Brain 2
            "brain2_called":     b2_result is not None,
            "brain2_action":     b2_result.get("action")     if b2_result else None,
            "brain2_target":     b2_result.get("action_target") if b2_result else None,
            "brain2_confidence": b2_result.get("confidence") if b2_result else None,
            "brain2_threat":     b2_result.get("threat_summary") if b2_result else None,
            "brain2_reasoning":  b2_result.get("reasoning")  if b2_result else None,
        }
        records.append(rec)

    print(f"\n{'='*60}")
    print(f"Done. Brain 2 called {brain2_calls}/{len(spikes)} steps "
          f"(threshold: risk >= {BRAIN2_THRESHOLD})")

    # Save log
    out_path = ROOT / "data" / "llm_agent_log.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"Log saved → {out_path}")

    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Two-brain grid agent")
    parser.add_argument("--steps",      type=int,  default=None)
    parser.add_argument("--top-spikes", action="store_true")
    args = parser.parse_args()

    run_with_llm_agent(steps=args.steps, top_spikes=args.top_spikes)