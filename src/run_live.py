"""
Live Grid Simulation
====================
Runs the Pepco DC grid continuously, one simulated hour per tick.
Load levels follow a 24-hour demand curve that cycles automatically.
The agent watches each tick and prints advisories when conditions change.

Stop at any time with Ctrl+C.

Usage:
    python run_live.py                  # 1 tick per second (default)
    python run_live.py --speed 0.25     # fast mode (4 ticks/sec)
    python run_live.py --speed 5        # slow mode (1 tick per 5 sec)
    python run_live.py --ticks 48       # run exactly 48 hours then stop
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from simulator.brain1 import score as brain1
from simulator.brain2 import run as brain2
from src.simulation import SimulationEnvironment

# ── 24-hour load multiplier profile ───────────────────────────────────────────
# Scales the baseline grid load each simulated hour.
# 1.0 = baseline (1,182 MW). Peak at hour 18 (~1,480 MW). Trough at hour 4 (~780 MW).
LOAD_PROFILE = [
    0.66,  # 00:00 — overnight low
    0.63,  # 01:00
    0.61,  # 02:00
    0.60,  # 03:00
    0.60,  # 04:00 — trough
    0.62,  # 05:00
    0.68,  # 06:00 — morning ramp
    0.78,  # 07:00
    0.88,  # 08:00
    0.94,  # 09:00
    0.97,  # 10:00
    0.99,  # 11:00
    1.00,  # 12:00 — midday
    1.01,  # 13:00
    1.03,  # 14:00
    1.07,  # 15:00
    1.12,  # 16:00 — afternoon build
    1.18,  # 17:00
    1.22,  # 18:00
    1.25,  # 19:00 — evening peak
    1.20,  # 20:00
    1.10,  # 21:00
    0.95,  # 22:00
    0.78,  # 23:00
]


def apply_load_profile(env: SimulationEnvironment, hour: int) -> None:
    """Scale all static loads to the current hour's demand multiplier."""
    multiplier = LOAD_PROFILE[hour % 24]
    net = env.grid.net
    for idx in net.load.index:
        name = net.load.loc[idx, "name"]
        # Don't scale the flexible load — agent controls that directly
        if name == "DC_NoMa":
            continue
        # Scale from the original baseline stored in grid.load_specs
        spec_name = name.replace(" Load", "")
        if spec_name in env.grid.load_specs:
            baseline = env.grid.load_specs[spec_name].p_mw
        else:
            baseline = net.load.loc[idx, "p_mw"]
        net.load.loc[idx, "p_mw"] = baseline * multiplier


def print_tick(tick: int, hour: int, state: dict, agent_result: dict,
               multiplier: float) -> None:
    """Print a single-line live status for this tick."""
    sep = "─" * 70

    total_load = state["total_load_mw"]
    total_gen  = state["total_gen_mw"] + state["total_sgen_mw"]
    reserve    = total_gen - total_load
    max_line   = state["max_line_loading_pct"]
    v_min      = state["min_bus_voltage_pu"]

    # Agent action taken this tick
    actions = []
    if agent_result:
        actions = [a["action"] for a in agent_result.get("actions", [])]
    action_str = ", ".join(actions) if actions else "nominal"

    # Violation indicator
    violations = []
    if agent_result:
        v = agent_result.get("violations", {})
        if v.get("line_loading"):  violations.append("LINE OVERLOAD")
        if v.get("voltage_min"):   violations.append("LOW VOLTAGE")
        if v.get("reserve_margin"):violations.append("LOW RESERVE")
    alert = f"  ⚠  {', '.join(violations)}" if violations else ""

    print(sep)
    print(f"  Tick {tick:>4}  |  {hour:02d}:00  |  Load ×{multiplier:.2f}")
    print(f"  Load     : {total_load:>7.1f} MW    Generation : {total_gen:>7.1f} MW")
    print(f"  Reserve  : {reserve:>7.1f} MW    Line max   : {max_line:>6.1f}%")
    print(f"  V min    : {v_min:.4f} p.u.   Agent      : {action_str}{alert}")


def run_live(tick_seconds: float = 1.0, max_ticks: int = None) -> None:
    print("\n" + "=" * 70)
    print("  PEPCO DC GRID — LIVE SIMULATION")
    print("  Press Ctrl+C to stop")
    print("=" * 70 + "\n")

    env = SimulationEnvironment()
    env.build_grid()
    env.initialize()

    tick = 0
    try:
        while True:
            if max_ticks is not None and tick >= max_ticks:
                print(f"\n[LIVE] Reached {max_ticks} ticks — stopping.")
                break

            hour = tick % 24
            multiplier = LOAD_PROFILE[hour]

            # Update load levels for this hour
            apply_load_profile(env, hour)

            # Step: power flow + agent
            result = env.step(apply_agent=True)

            # ── Two-brain agent ──────────────────────────────────
            pf = result.get("pf_report") or {}
            agent = result.get("agent_result") or {}

            risk = brain1(pf, result)
            if risk["action_needed"]:
                b2 = brain2(risk, agent, tick)
                print(f"\n  [BRAIN2] action     : {b2['action']} → {b2['action_target']}")
                print(f"  [BRAIN2] threat     : {b2['threat_summary']}")
                print(f"  [BRAIN2] reasoning  : {b2['reasoning']}")
                print(f"  [BRAIN2] confidence : {b2['confidence']}\n")
            if not result.get("converged"):
                print(f"[LIVE] Power flow failed at tick {tick} — stopping.")
                break

            print_tick(
                tick=tick,
                hour=hour,
                state=result["grid_state"],
                agent_result=result.get("agent_result"),
                multiplier=multiplier,
            )

            tick += 1
            time.sleep(tick_seconds)

    except KeyboardInterrupt:
        print(f"\n\n[LIVE] Stopped by operator after {tick} ticks "
              f"({tick} simulated hours).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--speed", type=float, default=1.0,
        help="Seconds per tick (default 1.0). Lower = faster.",
    )
    parser.add_argument(
        "--ticks", type=int, default=None,
        help="Stop after N ticks (default: run forever).",
    )
    args = parser.parse_args()
    run_live(tick_seconds=args.speed, max_ticks=args.ticks)
