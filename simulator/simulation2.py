"""
Simple Regional Grid — Simulation 2
=====================================
A minimal 3-transmission / 12-distribution substation grid.
Demonstrates the agent and power flow engine work with any topology.

Compare with simulation1.py (Pepco DC, 58 buses, 51 transformers) to see
that the same agent works unchanged on a completely different grid layout.

Topology:
  - 3  transmission substations (115 kV)
  - 12 distribution substations (13.8 kV)  — 15 buses total
  - 4  transmission lines (ring + 1 cross-tie)
  - 12 transformers (115 / 13.8 kV)
  - 2  generators (~500 MW; TX_North is slack)
  - 12 static loads (~248 MW peak)
  - 2  DER units (25 MW)
  - 1  flexible load (data center, 30 MW baseline)

Usage:
    python simulator/simulation2.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pandapower as pp
from typing import Dict, List, Optional

from simulator.network import (
    GridNetwork, BusSpec, LineSpec, GeneratorSpec,
    LoadSpec, FlexibleLoadSpec, StaticGeneratorSpec,
)
from simulator.power_flow import PowerFlowEngine
from agent.agent import GridOptimizationAgent


class SimpleGridEnvironment:
    """
    Simulation environment for a small regional grid.
    Same interface as SimulationEnvironment in simulation1.py —
    the agent plugs in identically.
    """

    def __init__(self, grid_name: str = "Simple Regional Grid"):
        self.grid_name = grid_name
        self.grid:      Optional[GridNetwork]           = None
        self.pf_engine: Optional[PowerFlowEngine]       = None
        self.agent:     Optional[GridOptimizationAgent] = None
        self.flex_load  = None
        self.scenario_history: List[Dict] = []
        self.current_time_step = 0

    def build_grid(self):
        self.grid = GridNetwork(name=self.grid_name)
        net = self.grid.net

        # ── Transmission substations (115 kV) ─────────────────────────────────
        for name in ["TX_North", "TX_Central", "TX_South"]:
            self.grid.add_bus(BusSpec(name=name, vn_kv=115.0, zone="TX"))

        # ── Distribution substations (13.8 kV) — 4 per transmission bus ───────
        for name in [
            "DIST_01", "DIST_02", "DIST_03", "DIST_04",   # TX_North
            "DIST_05", "DIST_06", "DIST_07", "DIST_08",   # TX_Central
            "DIST_09", "DIST_10", "DIST_11", "DIST_12",   # TX_South
        ]:
            self.grid.add_bus(BusSpec(name=name, vn_kv=13.8, zone="DIST"))

        # ── Transmission lines (115 kV, 150 MVA) ──────────────────────────────
        _r, _x, _c, _sn = 0.05, 0.35, 9.0, 150.0
        for lname, fb, tb, km in [
            ("LINE_North-Central",  "TX_North",   "TX_Central",  8.0),
            ("LINE_Central-South",  "TX_Central", "TX_South",    7.0),
            ("LINE_South-North",    "TX_South",   "TX_North",   12.0),
            ("LINE_North-South_XB", "TX_North",   "TX_South",   10.0),  # cross-tie
        ]:
            self.grid.add_line(LineSpec(lname, fb, tb, km, _r, _x, _c, _sn))

        # ── 115 / 13.8 kV transformers ────────────────────────────────────────
        for hv, lv, sn_mva in [
            ("TX_North",   "DIST_01", 30), ("TX_North",   "DIST_02", 30),
            ("TX_North",   "DIST_03", 25), ("TX_North",   "DIST_04", 25),
            ("TX_Central", "DIST_05", 40), ("TX_Central", "DIST_06", 35),
            ("TX_Central", "DIST_07", 30), ("TX_Central", "DIST_08", 30),
            ("TX_South",   "DIST_09", 30), ("TX_South",   "DIST_10", 25),
            ("TX_South",   "DIST_11", 25), ("TX_South",   "DIST_12", 20),
        ]:
            hv_idx = net.bus[net.bus["name"] == hv].index[0]
            lv_idx = net.bus[net.bus["name"] == lv].index[0]
            pp.create_transformer_from_parameters(
                net, hv_bus=hv_idx, lv_bus=lv_idx,
                sn_mva=float(sn_mva), vn_hv_kv=115.0, vn_lv_kv=13.8,
                vkr_percent=0.3, vk_percent=8.0, pfe_kw=20.0,
                i0_percent=0.08, name=f"TR_{lv}",
            )

        # ── Generators ────────────────────────────────────────────────────────
        self.grid.add_generator(GeneratorSpec(
            name="Gen_North", bus="TX_North",
            p_mw=300.0, slack=True, p_min_mw=0.0, p_max_mw=600.0,
        ))
        self.grid.add_generator(GeneratorSpec(
            name="Gen_South", bus="TX_South",
            p_mw=200.0, slack=False, p_min_mw=0.0, p_max_mw=350.0,
        ))

        # ── Static loads (~248 MW peak) ───────────────────────────────────────
        for lname, bus, p_mw in [
            ("Load_01", "DIST_01", 22.0),
            ("Load_02", "DIST_02", 18.0),
            ("Load_03", "DIST_03", 20.0),
            ("Load_04", "DIST_04", 15.0),
            ("Load_05", "DIST_05", 30.0),
            ("Load_06", "DIST_06", 28.0),
            ("Load_07", "DIST_07", 25.0),
            ("Load_08", "DIST_08", 22.0),
            ("Load_09", "DIST_09", 20.0),
            ("Load_10", "DIST_10", 18.0),
            ("Load_11", "DIST_11", 16.0),
            ("Load_12", "DIST_12", 14.0),
        ]:
            self.grid.add_load(LoadSpec(name=lname, bus=bus, p_mw=p_mw))

        # ── DER (25 MW total) ─────────────────────────────────────────────────
        self.grid.add_static_gen(StaticGeneratorSpec(
            name="DER_Central", bus="DIST_06", p_mw=15.0))
        self.grid.add_static_gen(StaticGeneratorSpec(
            name="DER_South",   bus="DIST_10", p_mw=10.0))

        # ── Flexible load — data center on DIST_05 ────────────────────────────
        self.flex_load = self.grid.add_flexible_load(FlexibleLoadSpec(
            name="DC_Central",
            bus="DIST_05",
            baseline_mw=30.0,
            min_mw=15.0,
            max_mw=45.0,
            deferrable_pct=0.30,
            defer_window_hours=4,
        ))

        print(f"[ENV] Grid '{self.grid_name}' built:")
        print(f"      {len(net.bus):>3} buses  (TX={len(net.bus[net.bus['vn_kv']==115.0])}, dist={len(net.bus[net.bus['vn_kv']==13.8])})")
        print(f"      {len(net.line):>3} transmission lines")
        print(f"      {len(net.trafo):>3} transformers (115/13.8 kV)")
        print(f"      {len(net.gen):>3} generators  ({net.gen['p_mw'].sum():.0f} MW)")
        print(f"      {len(net.load):>3} static loads ({net.load['p_mw'].sum():.0f} MW peak)")
        print(f"      {len(net.sgen):>3} DER units   ({net.sgen['p_mw'].sum():.0f} MW)")

    def initialize(self):
        if self.grid is None:
            raise RuntimeError("Call build_grid() first")
        self.pf_engine = PowerFlowEngine(self.grid)
        self.agent     = GridOptimizationAgent(self.grid, self.pf_engine)
        if not self.pf_engine.run():
            raise RuntimeError("Initial power flow failed to converge")
        print("[ENV] Initialization complete. Initial power flow converged.")

    def step(self, apply_agent: bool = True) -> Dict:
        if self.grid is None or self.pf_engine is None:
            raise RuntimeError("Call initialize() first")

        result = {
            "time_step":    self.current_time_step,
            "grid_state":   None,
            "pf_report":    None,
            "agent_result": None,
            "converged":    False,
        }

        if not self.pf_engine.run():
            print(f"[STEP {self.current_time_step}] Power flow FAILED")
            return result

        result["pf_report"]  = self.pf_engine.generate_report()
        result["grid_state"] = self.grid.get_state_summary()
        result["converged"]  = True

        if apply_agent and self.agent:
            state = result["grid_state"]
            result["agent_result"] = self.agent.step(
                flex_loads={"DC_Central": self.flex_load},
                current_load_mw=state["total_load_mw"],
                current_hour=self.current_time_step % 24,
                current_reserve_mw=(
                    state["total_gen_mw"] + state["total_sgen_mw"]
                    - state["total_load_mw"]
                ),
            )

        self.scenario_history.append(result)
        self.current_time_step += 1
        return result

    def debug_check(self):
        if self.grid is None:
            print("[DEBUG] Grid not built.")
            return

        net = self.grid.net
        sep = "─" * 60
        print(f"\n{sep}")
        print(f"  DEBUG CHECK — {self.grid.name}")
        print(sep)

        print(f"\n[1] Topology")
        print(f"    Buses        : {len(net.bus):>3}  expected 15")
        print(f"    TX lines     : {len(net.line):>3}  expected 4")
        print(f"    Transformers : {len(net.trafo):>3}  expected 12")
        print(f"    Generators   : {len(net.gen):>3}  expected 2")
        print(f"    Static loads : {len(net.load):>3}  expected 12")
        print(f"    DER (sgen)   : {len(net.sgen):>3}  expected 2")
        ok = (len(net.bus) == 15 and len(net.line) == 4 and
              len(net.trafo) == 12 and len(net.gen) == 2 and len(net.load) == 12)
        print(f"    {'✓ Counts correct' if ok else '✗ Count mismatch'}")

        print(f"\n[2] Power Flow")
        try:
            pp.runpp(net, check_convergence=True, numba=False)
            print(f"    ✓ Converged")
        except Exception as exc:
            print(f"    ✗ FAILED: {exc}")
            return

        v = net.res_bus["vm_pu"]
        print(f"\n[3] Voltage  range: {v.min():.4f} – {v.max():.4f} p.u.")

        t = net.res_trafo["loading_percent"]
        print(f"\n[4] Transformers  max: {t.max():.1f}%  mean: {t.mean():.1f}%")

        l = net.res_line["loading_percent"]
        print(f"\n[5] Lines  max: {l.max():.1f}%  mean: {l.mean():.1f}%")

        print(f"\n{sep}\n")


if __name__ == "__main__":
    env = SimpleGridEnvironment()
    env.build_grid()
    env.debug_check()
