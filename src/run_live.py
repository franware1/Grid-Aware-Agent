"""
Live Grid Simulation
====================
Runs any SimulationEnvironment continuously, one simulated hour per tick.
Load levels follow a 24-hour demand curve that cycles automatically.
The agent watches each tick and prints advisories when conditions change.

Stop at any time with Ctrl+C.

Usage:
    python src/run_live.py                        # simulation1, 1 tick/sec
    python src/run_live.py --grid 2               # simulation2
    python src/run_live.py --grid 1 --speed 0.25  # fast mode (4 ticks/sec)
    python src/run_live.py --grid 2 --ticks 48    # run exactly 48 hours then stop
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 24-hour load multiplier profile ───────────────────────────────────────────
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

# ── Grid registry — add new simulations here ──────────────────────────────────

def _load_env(grid_id: int):
    """Instantiate the requested grid environment."""
    if grid_id == 1:
        from simulator.simulation1 import SimulationEnvironment
        return SimulationEnvironment()
    elif grid_id == 2:
        from simulator.simulation2 import SimpleGridEnvironment
        return SimpleGridEnvironment()
    else:
        raise ValueError(
            f"Unknown grid '{grid_id}'. Available: 1 (Pepco DC), 2 (Simple Regional)"
        )


def apply_load_profile(env, hour: int) -> None:
    """Scale all static loads to the current hour's multiplier.
    Skips flexible loads — the agent controls those directly."""
    multiplier = LOAD_PROFILE[hour % 24]
    net        = env.grid.net
    flex_names = set(env.grid.flex_load_specs.keys())

    for idx in net.load.index:
        name = net.load.loc[idx, "name"]
        if name in flex_names:
            continue
        spec_name = name.replace(" Load", "")
        if spec_name in env.grid.load_specs:
            baseline = env.grid.load_specs[spec_name].p_mw
        else:
            baseline = net.load.loc[idx, "p_mw"]
        net.load.loc[idx, "p_mw"] = baseline * multiplier


def print_tick(tick: int, hour: int, state: dict, agent_result: dict,
               multiplier: float, grid_name: str) -> None:
    sep        = "─" * 70
    total_load = state["total_load_mw"]
    total_gen  = state["total_gen_mw"] + state["total_sgen_mw"]
    reserve    = total_gen - total_load
    max_line   = state["max_line_loading_pct"]
    v_min      = state["min_bus_voltage_pu"]

    actions    = [a["action"] for a in (agent_result or {}).get("actions", [])]
    action_str = ", ".join(actions) if actions else "nominal"

    violations = []
    if agent_result:
        v = agent_result.get("violations", {})
        if v.get("line_loading"):   violations.append("LINE OVERLOAD")
        if v.get("voltage_min"):    violations.append("LOW VOLTAGE")
        if v.get("reserve_margin"): violations.append("LOW RESERVE")
    alert = f"  ⚠  {', '.join(violations)}" if violations else ""

    print(sep)
    print(f"  [{grid_name}]  Tick {tick:>4}  |  {hour:02d}:00  |  Load x{multiplier:.2f}")
    print(f"  Load     : {total_load:>7.1f} MW    Generation : {total_gen:>7.1f} MW")
    print(f"  Reserve  : {reserve:>7.1f} MW    Line max   : {max_line:>6.1f}%")
    print(f"  V min    : {v_min:.4f} p.u.   Agent      : {action_str}{alert}")


def run_live(env, tick_seconds: float = 1.0, max_ticks: int = None) -> None:
    """
    Run a live simulation loop on any environment object.

    Args:
        env:          Any SimulationEnvironment-like object — already built
                      and initialized. Must expose .step() and .grid.
        tick_seconds: Real-world seconds between ticks.
        max_ticks:    Stop after N ticks (None = run forever).
    """
    print("\n" + "=" * 70)
    print(f"  {env.grid.name.upper()} — LIVE SIMULATION")
    print("  Press Ctrl+C to stop")
    print("=" * 70 + "\n")

    tick = 0
    try:
        while True:
            if max_ticks is not None and tick >= max_ticks:
                print(f"\n[LIVE] Reached {max_ticks} ticks — stopping.")
                break

            hour       = tick % 24
            multiplier = LOAD_PROFILE[hour]

            apply_load_profile(env, hour)
            result = env.step(apply_agent=True)

            if not result.get("converged"):
                print(f"[LIVE] Power flow failed at tick {tick} — stopping.")
                break

            print_tick(
                tick=tick,
                hour=hour,
                state=result["grid_state"],
                agent_result=result.get("agent_result"),
                multiplier=multiplier,
                grid_name=env.grid.name,
            )

            tick += 1
            time.sleep(tick_seconds)

    except KeyboardInterrupt:
        print(f"\n\n[LIVE] Stopped by operator after {tick} ticks "
              f"({tick} simulated hours).\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live grid simulation.")
    parser.add_argument(
        "--grid", type=int, default=1, choices=[1, 2],
        help="Which grid to run: 1=Pepco DC (58 buses), 2=Simple Regional (15 buses). Default: 1",
    )
    parser.add_argument(
        "--speed", type=float, default=1.0,
        help="Seconds per tick (default 1.0). Lower = faster.",
    )
    parser.add_argument(
        "--ticks", type=int, default=None,
        help="Stop after N ticks (default: run forever).",
    )
    args = parser.parse_args()

    env = _load_env(args.grid)
    env.build_grid()
    env.initialize()

    run_live(env, tick_seconds=args.speed, max_ticks=args.ticks)
