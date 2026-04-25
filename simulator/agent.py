"""
Rule-based grid optimization agent.
Watches constraint violations and decides how to use flexible loads
(data center curtailment/deferral) to relieve stress.
"""

from typing import Dict, Optional


class GridOptimizationAgent:
    """
    Heuristic agent: curtails or defers flexible loads when constraints fire.

    Actions (in priority order):
      1. If reserve margin is low → defer deferrable load on all flex loads.
      2. If a line is overloaded → curtail flex loads connected to that bus.
      3. If voltage is low → curtail flex loads to reduce reactive demand.
      4. Otherwise → restore flex loads to baseline.
    """

    RESERVE_LOW_MW = 350.0    # Trigger deferral when reserve drops below this
    CURTAIL_PCT    = 0.20     # Curtail 20% of baseline under stress
    DEFER_PCT      = 0.15     # Defer 15% of baseline when reserve is tight

    def __init__(self, grid, pf_engine):
        self.grid = grid
        self.pf_engine = pf_engine

    def step(
        self,
        flex_loads: Dict,
        current_load_mw: float,
        current_hour: int,
        current_reserve_mw: float,
    ) -> Dict:
        """
        Evaluate grid state and apply load management actions.

        Returns a dict describing what action was taken and why.
        """
        violations = self.pf_engine.check_constraints()
        actions_taken = []

        reserve_stressed   = current_reserve_mw < self.RESERVE_LOW_MW
        line_overloaded    = violations.get("line_loading", False)
        voltage_low        = violations.get("voltage_min", False)

        for name, flex in flex_loads.items():
            if line_overloaded or voltage_low:
                ok = flex.curtail_load(self.CURTAIL_PCT)
                actions_taken.append({
                    "load": name,
                    "action": "curtail",
                    "pct": self.CURTAIL_PCT,
                    "success": ok,
                    "reason": "line_overload" if line_overloaded else "low_voltage",
                })
            elif reserve_stressed:
                ok = flex.defer_load(flex.baseline_mw * self.DEFER_PCT)
                actions_taken.append({
                    "load": name,
                    "action": "defer",
                    "mw": flex.baseline_mw * self.DEFER_PCT,
                    "success": ok,
                    "reason": "low_reserve",
                })
            else:
                flex.restore_baseline()
                actions_taken.append({
                    "load": name,
                    "action": "restore",
                    "success": True,
                    "reason": "nominal",
                })

        return {
            "reserve_mw": current_reserve_mw,
            "violations": violations,
            "actions": actions_taken,
        }
