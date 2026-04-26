"""
Live Grid Simulation
====================
Runs the Pepco DC grid continuously, one simulated 10-minute interval per tick.
Load levels follow a 24-hour demand curve (144 ticks/day) that cycles automatically.
When an event fires, the simulation pauses and Brain 2 presents an action menu
to the operator. Whatever choice the operator makes, the event is resolved.
If no response is received within 5 minutes, the event persists.

Stop at any time with Ctrl+C.

Usage:
    python run_live.py                  # 1 tick per second (default)
    python run_live.py --speed 0.25     # fast mode (4 ticks/sec)
    python run_live.py --speed 5        # slow mode (1 tick per 5 sec)
    python run_live.py --ticks 288      # run exactly 2 simulated days then stop
"""

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))         # src/
sys.path.insert(0, str(Path(__file__).parent.parent))  # project root (for simulator/)

from simulator.brain1 import score as brain1
from simulator.brain2 import run as brain2
from simulator.events import EventScheduler, GridEvent, EventType
from simulator.build_simulation import SimulationEnvironment

TICKS_PER_HOUR = 6    # 1 tick = 10 minutes
TICKS_PER_DAY  = 144  # 24 hours × 6 ticks/hour

# ── 24-hour hourly load multiplier anchors ─────────────────────────────────────
# Calibrated for 10-min resolution. 1.0 = baseline (~1,182 MW).
# Range 0.77–1.16 reflects real utility zone trough-to-peak ratio (~1.5×).
# Steepest ramp (07:00–09:00) produces ~1.2%/10 min — consistent with PJM DOM data.
# Fastest decay (21:00–23:00) ~1.5%/10 min — load drops quickly at end of business day.
_HOURLY = [
    0.81,  # 00:00 — late night
    0.80,  # 01:00
    0.79,  # 02:00
    0.78,  # 03:00
    0.77,  # 04:00 — overnight trough
    0.78,  # 05:00 — pre-dawn uptick
    0.81,  # 06:00 — morning start    (+0.5%/10 min)
    0.88,  # 07:00 — steep ramp       (+1.2%/10 min)
    0.95,  # 08:00                    (+1.2%/10 min)
    1.00,  # 09:00 — approaches peak  (+0.8%/10 min)
    1.02,  # 10:00 — plateau          (+0.3%/10 min)
    1.03,  # 11:00
    1.03,  # 12:00 — midday plateau
    1.04,  # 13:00
    1.05,  # 14:00
    1.07,  # 15:00 — afternoon build  (+0.3%/10 min)
    1.10,  # 16:00                    (+0.5%/10 min)
    1.13,  # 17:00                    (+0.5%/10 min)
    1.15,  # 18:00                    (+0.3%/10 min)
    1.16,  # 19:00 — evening peak     (+0.2%/10 min)
    1.14,  # 20:00 — begin decay      (-0.3%/10 min)
    1.09,  # 21:00                    (-0.8%/10 min)
    1.00,  # 22:00                    (-1.5%/10 min)
    0.90,  # 23:00 — fast evening drop (-1.5%/10 min → wraps to 00:00 at -1.5%/10 min)
]

# Linearly interpolate hourly anchors to 10-minute resolution (144 entries).
LOAD_PROFILE = []
for _i in range(TICKS_PER_DAY):
    _h    = _i // TICKS_PER_HOUR
    _frac = (_i % TICKS_PER_HOUR) / TICKS_PER_HOUR
    _v0   = _HOURLY[_h]
    _v1   = _HOURLY[(_h + 1) % 24]
    LOAD_PROFILE.append(round(_v0 + _frac * (_v1 - _v0), 4))

# Real-time window the operator has to respond before the simulation resumes.
# If no input is received, the event persists until its natural duration expires.
OPERATOR_TIMEOUT_SECONDS = 300  # 5 minutes


# ── Demo event schedule ───────────────────────────────────────────────────────
# Four AI data center events on DC_NoMa spaced across one 24-hour cycle.
# scheduled_at and duration_steps are in ticks (1 tick = 10 min).
# cooling_delay and period_steps are left in tick units intentionally:
#   cooling_delay=3  → 30-minute thermal lag (realistic for CRAC units)
#   period_steps=4   → 40-minute oscillation cycle (realistic for VFD hunting)
DEMO_SCHEDULE = [
    # Tick 36 (06:00 day 1) — morning training job launches with unknown magnitude
    GridEvent(
        name="demo_ai_training_spike",
        event_type=EventType.AI_TRAINING_SPIKE,
        target="DC_NoMa",
        scheduled_at=36.0,
        duration_steps=24,   # 4 hours
        params={"min_mw": 25.0, "max_mw": 60.0},
    ),
    # Tick 84 (14:00 day 1) — training job crashes mid-afternoon, 75% load drops instantly
    GridEvent(
        name="demo_ai_training_dropout",
        event_type=EventType.AI_TRAINING_DROPOUT,
        target="DC_NoMa",
        scheduled_at=84.0,
        duration_steps=18,   # 3 hours
        params={"dropout_pct": 0.75},
    ),
    # Tick 108 (18:00 day 1) — compute surge at evening peak, cooling kicks in 30 min later
    GridEvent(
        name="demo_cooling_cascade",
        event_type=EventType.COOLING_CASCADE,
        target="DC_NoMa",
        scheduled_at=108.0,
        duration_steps=36,   # 6 hours
        params={"compute_mw": 40.0, "cooling_delay": 3, "cooling_mw": 18.0},
    ),
    # Tick 180 (06:00 day 2) — power-electronics hunting during morning ramp
    GridEvent(
        name="demo_load_oscillation",
        event_type=EventType.LOAD_OSCILLATION,
        target="DC_NoMa",
        scheduled_at=180.0,
        duration_steps=48,   # 8 hours
        params={"amplitude_mw": 15.0, "period_steps": 4.0},
    ),
]


# ── Operator console helpers ──────────────────────────────────────────────────

def _timed_input(prompt: str, timeout: float) -> str:
    """Read a line from stdin with a wall-clock timeout. Returns '' on timeout."""
    result = [None]

    def _read():
        try:
            result[0] = input(prompt)
        except EOFError:
            result[0] = ""

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return result[0] if result[0] is not None else ""


def _operator_console(ev: GridEvent, b2: dict, scheduler: EventScheduler) -> str:
    """
    Brain 2 presents a numbered action menu to the operator.
    Any valid key (1-4 or Enter) triggers resolve_event().
    Timeout → event persists. Returns the operator's raw response string.
    """
    bar   = "=" * 70
    tmin  = OPERATOR_TIMEOUT_SECONDS // 60

    print(f"\n{bar}")
    print(f"  [BRAIN 2 — OPERATOR ACTION REQUIRED]")
    print(f"  {'─' * 66}")
    print(f"  Event      : {ev.name}  ({ev.event_type.value})")
    print(f"  Target     : {ev.target}")
    print(f"  {'─' * 66}")
    print(f"  THREAT     : {b2['threat_summary']}")
    print(f"  REASONING  : {b2['reasoning']}")
    print(f"  CONFIDENCE : {b2['confidence']}")
    print(f"  {'─' * 66}")
    print(f"  RECOMMENDATION  →  {b2['action']}  on  {b2['action_target']}")
    print(f"  {'─' * 66}")
    print(f"  Choose an action ({tmin}-min timeout — no response = event persists):\n")
    print(f"    [1]  {b2['action'].upper()} on {b2['action_target']}  ← Brain 2 recommendation")
    print(f"    [2]  DEFER_WORKLOAD   — postpone deferrable DC_NoMa jobs")
    print(f"    [3]  CURTAIL_LOAD     — reduce DC_NoMa below baseline now")
    print(f"    [4]  RESTORE_BASELINE — return DC_NoMa to normal draw")
    print(f"  [Enter]  Acknowledge and resolve\n")
    print(f"{bar}")

    response = _timed_input("  Operator selection: ", timeout=OPERATOR_TIMEOUT_SECONDS)

    if response is None or response.strip() == "" and response != "":
        # timeout
        print(f"\n  [BRAIN 2] No operator response in {tmin} min — event persists.\n")
        return ""

    choice = response.strip()

    if choice in ("1", "2", "3", "4", ""):
        labels = {
            "1": b2["action"],
            "2": "defer_workload",
            "3": "curtail_load",
            "4": "restore_baseline",
            "":  "acknowledge",
        }
        print(f"\n  [BRAIN 2] Operator selected: {labels[choice].upper()}")
        print(f"  [BRAIN 2] Executing resolve_event() on '{ev.name}'...")
        resolved = scheduler.force_resolve(ev.name)
        if resolved:
            print(f"  [BRAIN 2] Event resolved. Grid returning to baseline.\n")
        else:
            print(f"  [BRAIN 2] Warning: event already expired before resolution.\n")
    else:
        print(f"\n  [BRAIN 2] Unrecognized input — event persists.\n")

    return choice




# ── Event / tick display ──────────────────────────────────────────────────────

def _print_event_banner(ev: GridEvent, status: str) -> None:
    bar = "!" * 70
    print(f"\n{bar}")
    print(f"  [EVENT {status}]  {ev.name}")
    print(f"  Type    : {ev.event_type.value}")
    print(f"  Target  : {ev.target}")
    if ev.params:
        pairs = "  |  ".join(f"{k}={v}" for k, v in ev.params.items())
        print(f"  Params  : {pairs}")
    if status == "FIRED":
        print(f"  Duration: {ev.duration_steps} ticks ({ev.duration_steps * 10} min)")
    print(f"{bar}\n")


def _tick_to_time(tick: int) -> str:
    day_tick = tick % TICKS_PER_DAY
    hour     = day_tick // TICKS_PER_HOUR
    minute   = (day_tick % TICKS_PER_HOUR) * 10
    return f"{hour:02d}:{minute:02d}"


def apply_load_profile(env: SimulationEnvironment, day_tick: int) -> None:
    # Scale all static loads to the 10-minute slot's demand multiplier.
    multiplier = LOAD_PROFILE[day_tick]
    net = env.grid.net
    for idx in net.load.index:
        name = net.load.loc[idx, "name"]
        # Don't scale the flexible load — events control that directly
        if name == "DC_NoMa":
            continue
        spec_name = name.replace(" Load", "")
        if spec_name in env.grid.load_specs:
            baseline = env.grid.load_specs[spec_name].p_mw
        else:
            baseline = net.load.loc[idx, "p_mw"]
        net.load.loc[idx, "p_mw"] = baseline * multiplier


def print_tick(tick: int, time_str: str, state: dict, agent_result: dict,
               multiplier: float, active_events: list = None) -> None:
    sep = "─" * 70

    total_load = state["total_load_mw"]
    total_gen  = state["total_gen_mw"] + state["total_sgen_mw"]
    reserve    = state.get("reserve_margin_mw", 0.0)
    max_line   = state["max_line_loading_pct"]
    v_min      = state["min_bus_voltage_pu"]

    actions = []
    if agent_result:
        actions = [a["action"] for a in agent_result.get("actions", [])]
    action_str = ", ".join(actions) if actions else "nominal"

    violations = []
    if agent_result:
        v = agent_result.get("violations", {})
        if v.get("line_loading"):   violations.append("LINE OVERLOAD")
        if v.get("voltage_min"):    violations.append("LOW VOLTAGE")
        if v.get("reserve_margin"): violations.append("LOW RESERVE")
    alert = f"  ⚠  {', '.join(violations)}" if violations else ""

    print(sep)
    print(f"  Tick {tick:>5}  |  {time_str}  |  Load ×{multiplier:.4f}")
    print(f"  Load     : {total_load:>7.1f} MW    Generation : {total_gen:>7.1f} MW")
    print(f"  Reserve  : {reserve:>7.1f} MW    Line max   : {max_line:>6.1f}%")
    print(f"  V min    : {v_min:.4f} p.u.   Agent      : {action_str}{alert}")
    if active_events:
        ev_str = "  |  ".join(
            f"{e.event_type.value}@{e.target}" for e in active_events
        )
        print(f"  Active   : {ev_str}")


# ── Main live loop ────────────────────────────────────────────────────────────

def run_live(tick_seconds: float = 1.0, max_ticks: int = None) -> None:
    print("\n" + "=" * 70)
    print("  PEPCO DC GRID — LIVE SIMULATION  (10 min/tick)")
    print("  Press Ctrl+C to stop")
    print("=" * 70 + "\n")

    env = SimulationEnvironment()
    env.build_grid()
    env.initialize()

    scheduler = EventScheduler(env.grid)
    for ev in DEMO_SCHEDULE:
        scheduler.schedule(ev)
    print(f"[LIVE] {len(DEMO_SCHEDULE)} demo events scheduled.\n")

    tick = 0
    try:
        while True:
            if max_ticks is not None and tick >= max_ticks:
                print(f"\n[LIVE] Reached {max_ticks} ticks — stopping.")
                break

            day_tick   = tick % TICKS_PER_DAY
            time_str   = _tick_to_time(tick)
            multiplier = LOAD_PROFILE[day_tick]

            apply_load_profile(env, day_tick)

            event_results = scheduler.tick(float(tick))
            for ev in event_results["expired"]:
                _print_event_banner(ev, "CLEARED")

            # Run power flow first so Brain 1/2 see the real post-event grid state
            result = env.step()
            if not result.get("converged"):
                print(f"[LIVE] Power flow failed at tick {tick} — stopping.")
                break

            pf    = result.get("pf_report") or {}
            agent = result.get("agent_result") or {}
            risk  = brain1(pf, result)

            # For each newly fired event: print banner, run Brain 2, pause for operator
            for ev in event_results["applied"]:
                _print_event_banner(ev, "FIRED")
                b2 = brain2(risk, agent, tick)
                _operator_console(ev, b2, scheduler)

            # On non-event ticks where Brain 1 flags risk, show Brain 2 advisory
            if not event_results["applied"] and risk["action_needed"]:
                b2 = brain2(risk, agent, tick)
                print(f"\n  [BRAIN2] action     : {b2['action']} → {b2['action_target']}")
                print(f"  [BRAIN2] threat     : {b2['threat_summary']}")
                print(f"  [BRAIN2] reasoning  : {b2['reasoning']}")
                print(f"  [BRAIN2] confidence : {b2['confidence']}\n")

            print_tick(
                tick=tick,
                time_str=time_str,
                state=result["grid_state"],
                agent_result=agent,
                multiplier=multiplier,
                active_events=scheduler.active_events(),
            )

            tick += 1
            time.sleep(tick_seconds)

    except KeyboardInterrupt:
        elapsed_min = tick * 10
        print(f"\n\n[LIVE] Stopped by operator after {tick} ticks "
              f"({elapsed_min // 60}h {elapsed_min % 60}m simulated time).")


# ── Dashboard helper ──────────────────────────────────────────────────────────
# Run N ticks of the live simulation and return records for the dashboard.
# No operator prompts — events auto-expire at their natural duration.
# Default is one full simulated day (144 ticks × 10 min = 24 hours).
def run(ticks: int = 144) -> list:
    env = SimulationEnvironment()
    env.build_grid()
    env.initialize()

    scheduler = EventScheduler(env.grid)
    for ev in DEMO_SCHEDULE:
        scheduler.schedule(ev)

    records = []
    for tick in range(ticks):
        day_tick   = tick % TICKS_PER_DAY
        time_str   = _tick_to_time(tick)
        multiplier = LOAD_PROFILE[day_tick]
        apply_load_profile(env, day_tick)
        scheduler.tick(float(tick))

        result = env.step()
        pf     = result.get("pf_report") or {}
        state  = result.get("grid_state") or {}
        risk   = brain1(pf, result)

        b2_action = b2_target = b2_summary = b2_confidence = ""
        if risk["action_needed"]:
            b2            = brain2(risk, {}, tick)
            b2_action     = b2.get("action", "")
            b2_target     = b2.get("action_target", "")
            b2_summary    = b2.get("threat_summary", "")
            b2_confidence = b2.get("confidence", "")

        records.append({
            "tick":              tick,
            "hour":              time_str,
            "load_multiplier":   multiplier,
            "total_load_mw":     round(state.get("total_load_mw", 0), 1),
            "reserve_mw":        round(state.get("reserve_margin_mw", 0), 1),
            "line_loading_pct":  round(state.get("max_line_loading_pct", 0), 1),
            "min_voltage_pu":    round(state.get("min_bus_voltage_pu", 0), 4),
            "overall_risk":      risk["overall_risk"],
            "action_needed":     risk["action_needed"],
            "brain2_action":     b2_action,
            "brain2_target":     b2_target,
            "brain2_summary":    b2_summary,
            "brain2_confidence": b2_confidence,
            "n_violations":      pf.get("n_violations", 0),
            "converged":         result.get("converged", False),
            "active_events":     ", ".join(e.name for e in scheduler.active_events()),
        })

    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--speed", type=float, default=1.0,
        help="Seconds per tick (default 1.0). Lower = faster.",
    )
    parser.add_argument(
        "--ticks", type=int, default=None,
        help="Stop after N ticks (default: run indefinitely).",
    )
    args = parser.parse_args()
    run_live(tick_seconds=args.speed, max_ticks=args.ticks)
