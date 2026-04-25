"""
Integration: Simulation + Agent + Dashboard
=============================================
Ties together grid, power flow engine, and optimization agent.

This is the main orchestration module. Use it to:
  1. Create and configure your grid
  2. Run power flow
  3. Execute agent planning steps
  4. Generate reports for operator dashboard

Example Usage:
    from integration import SimulationEnvironment
    
    # Create environment
    env = SimulationEnvironment()
    
    # Build your grid (call your grid definition here)
    env.build_grid()
    
    # Run a single step
    result = env.step()
    
    # Run multiple steps (time stepping)
    results = env.run_scenario(steps=24)
"""

from typing import Dict, List, Optional, Tuple
import json
import pandapower as pp
from network import GridNetwork
from power_flow import PowerFlowEngine
from agent import GridOptimizationAgent


class SimulationEnvironment:
    """
    Main simulation environment: orchestrates grid, power flow, and agent.
    """
    
    def __init__(self, grid_name: str = "Pepco DC — Washington DC"):
        """Initialize the simulation environment."""
        self.grid_name = grid_name
        self.grid: Optional[GridNetwork] = None
        self.pf_engine: Optional[PowerFlowEngine] = None
        self.agent: Optional[GridOptimizationAgent] = None
        
        self.scenario_history: List[Dict] = []
        self.current_time_step = 0
    
    def build_grid(self):
        """
        Build the Pepco Washington DC grid.

        Topology (based on official Pepco system documentation):
          - 7  transmission substations at 115 kV  (PJM interconnect gateways)
          - 51 distribution substations at 13.8 kV (feeder dispatch nodes)
          - 10 transmission lines (ring + 3 cross-ties for N-1 reliability)
          - 51 transformers  (115 / 13.8 kV, 20–80 MVA)
          - 3  generators    (~1,200 MW combined; Benning Road is slack/PJM tie)
          - 51 static loads  (~1,182 MW peak, ~256,745 customers)
          - 6  DER sgens     (70 MW; concentrated in Mount Vernon / Navy Yard zone)
          - 1  flexible load (NoMa data-center hub, 80–140 MW, 25% deferrable)
        """
        from network import (
            BusSpec, LineSpec, GeneratorSpec, LoadSpec,
            FlexibleLoadSpec, StaticGeneratorSpec,
        )

        self.grid = GridNetwork(name=self.grid_name)
        net = self.grid.net

        # ── Transmission substations (115 kV) ─────────────────────────────────
        for name, zone in [
            ("Benning Road T",  "NE"),   # slack — primary PJM tie
            ("East Capitol T",  "SE"),
            ("Greenway T",      "SE"),
            ("Hains Point T",   "SW"),
            ("Buzzard Point T", "SW"),
            ("Georgetown T",    "NW"),
            ("Nevada Avenue T", "NW"),
        ]:
            self.grid.add_bus(BusSpec(name=name, vn_kv=115.0, zone=zone))

        # ── Distribution substations (13.8 kV) ────────────────────────────────
        for name, zone in [
            # Benning Road feeders — Northeast
            ("NoMa",               "NE"), ("H Street NE",        "NE"),
            ("Union Station",      "NE"), ("Brookland",          "NE"),
            ("Catholic Univ",      "NE"), ("Trinidad",           "NE"),
            ("Fort Lincoln",       "NE"), ("Gallaudet",          "NE"),
            # East Capitol feeders — Southeast
            ("Capitol Hill",       "SE"), ("Eastern Market",     "SE"),
            ("Navy Yard",          "SE"), ("Southeast",          "SE"),
            ("Barry Farm",         "SE"), ("Anacostia North",    "SE"),
            ("Fort Dupont",        "SE"), ("Benning Ridge",      "SE"),
            # Greenway feeders — Southeast
            ("Congress Heights",   "SE"), ("Hillcrest",          "SE"),
            ("Penn Branch",        "SE"), ("Woodland",           "SE"),
            ("Anacostia South",    "SE"), ("Shipley Terrace",    "SE"),
            ("Bellevue",           "SE"),
            # Hains Point feeders — Southwest / Central
            ("Southwest",          "SW"), ("Waterfront",         "SW"),
            ("L'Enfant Plaza",     "SW"), ("Federal Triangle",   "Downtown"),
            ("Farragut South",     "Downtown"), ("Foggy Bottom South", "NW"),
            ("Buzzard Point D",    "SW"),
            # Buzzard Point feeders — Downtown
            ("Penn Quarter",       "Downtown"), ("Downtown West",      "Downtown"),
            ("Chinatown",          "Downtown"), ("Mt Vernon Square",   "Downtown"),
            ("Shaw",               "NW"),  ("Howard Univ",        "NW"),
            ("LeDroit Park",       "NW"),
            # Georgetown feeders — Northwest
            ("Georgetown D",       "NW"),  ("Dupont Circle",      "NW"),
            ("Logan Circle",       "NW"),  ("Foggy Bottom",       "NW"),
            ("Watergate",          "NW"),  ("K Street",           "Downtown"),
            ("Farragut North",     "Downtown"),
            # Nevada Avenue feeders — Upper Northwest
            ("Cleveland Park",     "NW"),  ("Woodley Park",       "NW"),
            ("Columbia Heights",   "NW"),  ("Mount Pleasant",     "NW"),
            ("Adams Morgan",       "NW"),  ("Tenleytown",         "NW"),
            ("Friendship Heights", "NW"),
        ]:
            self.grid.add_bus(BusSpec(name=name, vn_kv=13.8, zone=zone))

        # ── Transmission lines (115 kV, ACSR overhead, 200 MVA) ───────────────
        _r, _x, _c, _sn = 0.0485, 0.350, 9.0, 200.0
        for lname, fb, tb, km in [
            # Ring
            ("TX_Benning-EastCapitol",  "Benning Road T",  "East Capitol T",  4.5),
            ("TX_EastCapitol-Greenway", "East Capitol T",  "Greenway T",      5.0),
            ("TX_Greenway-HainsPoint",  "Greenway T",      "Hains Point T",   4.0),
            ("TX_HainsPoint-Buzzard",   "Hains Point T",   "Buzzard Point T", 2.5),
            ("TX_Buzzard-Georgetown",   "Buzzard Point T", "Georgetown T",    3.5),
            ("TX_Georgetown-Nevada",    "Georgetown T",    "Nevada Avenue T", 6.0),
            ("TX_Nevada-Benning",       "Nevada Avenue T", "Benning Road T",  8.0),
            # Cross-ties for N-1 reliability
            ("TX_Benning-Georgetown",   "Benning Road T",  "Georgetown T",   10.0),
            ("TX_Nevada-HainsPoint",    "Nevada Avenue T", "Hains Point T",   8.0),
            ("TX_EastCapitol-Buzzard",  "East Capitol T",  "Buzzard Point T", 5.0),
        ]:
            self.grid.add_line(LineSpec(lname, fb, tb, km, _r, _x, _c, _sn))

        # ── 115 / 13.8 kV transformers ────────────────────────────────────────
        for hv, lv, sn_mva in [
            # Benning Road
            ("Benning Road T", "NoMa",               50), ("Benning Road T", "H Street NE",   40),
            ("Benning Road T", "Union Station",       60), ("Benning Road T", "Brookland",      30),
            ("Benning Road T", "Catholic Univ",       30), ("Benning Road T", "Trinidad",       30),
            ("Benning Road T", "Fort Lincoln",        30), ("Benning Road T", "Gallaudet",      25),
            # East Capitol
            ("East Capitol T", "Capitol Hill",        60), ("East Capitol T", "Eastern Market", 40),
            ("East Capitol T", "Navy Yard",           50), ("East Capitol T", "Southeast",      30),
            ("East Capitol T", "Barry Farm",          25), ("East Capitol T", "Anacostia North",30),
            ("East Capitol T", "Fort Dupont",         25), ("East Capitol T", "Benning Ridge",  25),
            # Greenway
            ("Greenway T", "Congress Heights",        25), ("Greenway T", "Hillcrest",          25),
            ("Greenway T", "Penn Branch",             25), ("Greenway T", "Woodland",           20),
            ("Greenway T", "Anacostia South",         25), ("Greenway T", "Shipley Terrace",    20),
            ("Greenway T", "Bellevue",                20),
            # Hains Point
            ("Hains Point T", "Southwest",            50), ("Hains Point T", "Waterfront",      60),
            ("Hains Point T", "L'Enfant Plaza",       80), ("Hains Point T", "Federal Triangle",80),
            ("Hains Point T", "Farragut South",       60), ("Hains Point T", "Foggy Bottom South",40),
            ("Hains Point T", "Buzzard Point D",      40),
            # Buzzard Point
            ("Buzzard Point T", "Penn Quarter",       80), ("Buzzard Point T", "Downtown West", 80),
            ("Buzzard Point T", "Chinatown",          60), ("Buzzard Point T", "Mt Vernon Square",50),
            ("Buzzard Point T", "Shaw",               40), ("Buzzard Point T", "Howard Univ",   30),
            ("Buzzard Point T", "LeDroit Park",       25),
            # Georgetown
            ("Georgetown T", "Georgetown D",          60), ("Georgetown T", "Dupont Circle",    60),
            ("Georgetown T", "Logan Circle",          40), ("Georgetown T", "Foggy Bottom",     50),
            ("Georgetown T", "Watergate",             40), ("Georgetown T", "K Street",         80),
            ("Georgetown T", "Farragut North",        60),
            # Nevada Avenue
            ("Nevada Avenue T", "Cleveland Park",     30), ("Nevada Avenue T", "Woodley Park",  35),
            ("Nevada Avenue T", "Columbia Heights",   40), ("Nevada Avenue T", "Mount Pleasant",30),
            ("Nevada Avenue T", "Adams Morgan",       40), ("Nevada Avenue T", "Tenleytown",    30),
            ("Nevada Avenue T", "Friendship Heights", 35),
        ]:
            hv_idx = net.bus[net.bus["name"] == hv].index[0]
            lv_idx = net.bus[net.bus["name"] == lv].index[0]
            pp.create_transformer_from_parameters(
                net, hv_bus=hv_idx, lv_bus=lv_idx,
                sn_mva=float(sn_mva), vn_hv_kv=115.0, vn_lv_kv=13.8,
                vkr_percent=0.3, vk_percent=8.0, pfe_kw=25.0,
                i0_percent=0.08, name=f"TR_{lv}",
            )

        # ── Generators (PJM ties) ──────────────────────────────────────────────
        for gname, bus, p_mw, slack, p_max in [
            ("Benning Road Gen",  "Benning Road T",  850.0, True,  1500.0),
            ("Georgetown Gen",    "Georgetown T",    200.0, False,  300.0),
            ("Buzzard Point Gen", "Buzzard Point T", 150.0, False,  250.0),
        ]:
            self.grid.add_generator(GeneratorSpec(
                name=gname, bus=bus, p_mw=p_mw, slack=slack,
                p_min_mw=0.0, p_max_mw=p_max,
            ))

        # ── Static loads (~1,182 MW total peak) ───────────────────────────────
        for lname, bus, p_mw in [
            ("NoMa Load",               "NoMa",               30.0),
            ("H Street NE Load",        "H Street NE",        20.0),
            ("Union Station Load",      "Union Station",      38.0),
            ("Brookland Load",          "Brookland",          13.0),
            ("Catholic Univ Load",      "Catholic Univ",      11.0),
            ("Trinidad Load",           "Trinidad",           15.0),
            ("Fort Lincoln Load",       "Fort Lincoln",       12.0),
            ("Gallaudet Load",          "Gallaudet",           9.0),
            ("Capitol Hill Load",       "Capitol Hill",       35.0),
            ("Eastern Market Load",     "Eastern Market",     24.0),
            ("Navy Yard Load",          "Navy Yard",          27.0),
            ("Southeast Load",          "Southeast",          16.0),
            ("Barry Farm Load",         "Barry Farm",         11.0),
            ("Anacostia North Load",    "Anacostia North",    13.0),
            ("Fort Dupont Load",        "Fort Dupont",        11.0),
            ("Benning Ridge Load",      "Benning Ridge",      10.0),
            ("Congress Heights Load",   "Congress Heights",   12.0),
            ("Hillcrest Load",          "Hillcrest",          11.0),
            ("Penn Branch Load",        "Penn Branch",        10.0),
            ("Woodland Load",           "Woodland",            9.0),
            ("Anacostia South Load",    "Anacostia South",    11.0),
            ("Shipley Terrace Load",    "Shipley Terrace",     9.0),
            ("Bellevue Load",           "Bellevue",           10.0),
            ("Southwest Load",          "Southwest",          30.0),
            ("Waterfront Load",         "Waterfront",         33.0),
            ("L'Enfant Plaza Load",     "L'Enfant Plaza",     44.0),
            ("Federal Triangle Load",   "Federal Triangle",   48.0),
            ("Farragut South Load",     "Farragut South",     38.0),
            ("Foggy Bottom South Load", "Foggy Bottom South", 24.0),
            ("Buzzard Point D Load",    "Buzzard Point D",    20.0),
            ("Penn Quarter Load",       "Penn Quarter",       48.0),
            ("Downtown West Load",      "Downtown West",      45.0),
            ("Chinatown Load",          "Chinatown",          40.0),
            ("Mt Vernon Square Load",   "Mt Vernon Square",   30.0),
            ("Shaw Load",               "Shaw",               22.0),
            ("Howard Univ Load",        "Howard Univ",        16.0),
            ("LeDroit Park Load",       "LeDroit Park",       13.0),
            ("Georgetown D Load",       "Georgetown D",       35.0),
            ("Dupont Circle Load",      "Dupont Circle",      38.0),
            ("Logan Circle Load",       "Logan Circle",       26.0),
            ("Foggy Bottom Load",       "Foggy Bottom",       30.0),
            ("Watergate Load",          "Watergate",          22.0),
            ("K Street Load",           "K Street",           44.0),
            ("Farragut North Load",     "Farragut North",     35.0),
            ("Cleveland Park Load",     "Cleveland Park",     15.0),
            ("Woodley Park Load",       "Woodley Park",       20.0),
            ("Columbia Heights Load",   "Columbia Heights",   24.0),
            ("Mount Pleasant Load",     "Mount Pleasant",     17.0),
            ("Adams Morgan Load",       "Adams Morgan",       22.0),
            ("Tenleytown Load",         "Tenleytown",         16.0),
            ("Friendship Heights Load", "Friendship Heights", 20.0),
        ]:
            self.grid.add_load(LoadSpec(name=lname, bus=bus, p_mw=p_mw))

        # ── DER — 70 MW, Mount Vernon / Navy Yard zone ────────────────────────
        for dname, bus, p_mw in [
            ("DER Mt Vernon Square", "Mt Vernon Square", 15.0),
            ("DER Navy Yard",        "Navy Yard",        20.0),
            ("DER Shaw",             "Shaw",             10.0),
            ("DER NoMa",             "NoMa",             12.0),
            ("DER Capitol Hill",     "Capitol Hill",      8.0),
            ("DER Howard Univ",      "Howard Univ",       5.0),
        ]:
            self.grid.add_static_gen(StaticGeneratorSpec(name=dname, bus=bus, p_mw=p_mw))

        # ── Flexible load — NoMa data-center hub ──────────────────────────────
        self.flex_load = self.grid.add_flexible_load(FlexibleLoadSpec(
            name="DC_NoMa",
            bus="NoMa",
            baseline_mw=110.0,
            min_mw=80.0,
            max_mw=140.0,
            deferrable_pct=0.25,
            defer_window_hours=4,
        ))

        print(f"[ENV] Grid '{self.grid_name}' built:")
        print(f"      {len(net.bus):>3} buses  ({len(net.bus[net.bus['vn_kv']==115.0])} transmission, {len(net.bus[net.bus['vn_kv']==13.8])} distribution)")
        print(f"      {len(net.line):>3} transmission lines")
        print(f"      {len(net.trafo):>3} transformers (115/13.8 kV)")
        print(f"      {len(net.gen):>3} generators  ({net.gen['p_mw'].sum():.0f} MW dispatched)")
        print(f"      {len(net.load):>3} static loads ({net.load['p_mw'].sum():.0f} MW peak)")
        print(f"      {len(net.sgen):>3} DER units   ({net.sgen['p_mw'].sum():.0f} MW)")
    
    def initialize(self):
        """Initialize power flow engine and agent after grid is built."""
        if self.grid is None:
            raise RuntimeError("Call build_grid() first")
        
        self.pf_engine = PowerFlowEngine(self.grid)
        self.agent = GridOptimizationAgent(self.grid, self.pf_engine)
        
        # Run initial power flow
        success = self.pf_engine.run()
        if not success:
            raise RuntimeError("Initial power flow failed to converge")
        
        print("[ENV] Initialization complete. Initial power flow converged.")
    
    def step(self, apply_agent: bool = True) -> Dict:
        """
        Execute one time step: power flow + optional agent planning.
        
        Args:
            apply_agent: If True, run agent step (forecast, plan, execute).
        
        Returns:
            Dictionary with step results.
        """
        if self.grid is None or self.pf_engine is None:
            raise RuntimeError("Call initialize() first")
        
        step_result = {
            'time_step': self.current_time_step,
            'grid_state': None,
            'pf_report': None,
            'agent_result': None,
        }
        
        # Power flow
        pf_success = self.pf_engine.run()
        if not pf_success:
            print(f"[STEP {self.current_time_step}] Power flow FAILED")
            step_result['converged'] = False
            return step_result
        
        # Generate power flow report
        pf_report = self.pf_engine.generate_report()
        step_result['pf_report'] = pf_report
        
        # Grid state summary
        state = self.grid.get_state_summary()
        step_result['grid_state'] = state
        
        # Agent step (optional)
        if apply_agent and self.agent is not None:
            flex_loads = {'DC_NoMa': self.flex_load}
            agent_result = self.agent.step(
                flex_loads=flex_loads,
                current_load_mw=state['total_load_mw'],
                current_hour=self.current_time_step % 24,
                current_reserve_mw=state['total_gen_mw'] + state['total_sgen_mw'] - state['total_load_mw'],
            )
            step_result['agent_result'] = agent_result
        
        step_result['converged'] = True
        
        # Log to history
        self.scenario_history.append(step_result)
        self.current_time_step += 1
        
        return step_result
    
    def run_scenario(
        self,
        steps: int = 24,
        apply_agent: bool = True,
        print_reports: bool = False,
    ) -> List[Dict]:
        """
        Run simulation for N time steps.
        
        Args:
            steps: Number of time steps to run
            apply_agent: Whether to apply agent at each step
            print_reports: Whether to print detailed reports
        
        Returns:
            List of step results.
        """
        print(f"\n[ENV] Running scenario for {steps} steps...")
        
        for _ in range(steps):
            result = self.step(apply_agent=apply_agent)
            
            if not result['converged']:
                print(f"[SCENARIO] Stopped at step {self.current_time_step} (convergence failure)")
                break
            
            if print_reports:
                self.pf_engine.print_report()
        
        print(f"[ENV] Scenario complete. {self.current_time_step} steps executed.")
        return self.scenario_history
    
    def get_scenario_summary(self) -> Dict:
        """Get summary statistics of the scenario."""
        if not self.scenario_history:
            return {'message': 'No scenario history'}
        
        summary = {
            'total_steps': len(self.scenario_history),
            'converged_steps': sum(1 for s in self.scenario_history if s.get('converged', False)),
            'agent_steps': sum(1 for s in self.scenario_history if s.get('agent_result') is not None),
            'peak_generation_mw': max(s['grid_state']['total_gen_mw'] for s in self.scenario_history),
            'peak_load_mw': max(s['grid_state']['total_load_mw'] for s in self.scenario_history),
            'max_line_loading_pct': max(
                s['pf_report']['summary'].get('max_line_loading_pct', 0.0)
                    for s in self.scenario_history
                if s.get('pf_report')
            ),
            'violations_recorded': sum(
                len(s['pf_report']['violations'])
                for s in self.scenario_history
                if s.get('pf_report')
            ),
        }
        
        return summary
    
    def export_history_json(self, filepath: str):
        """Export scenario history to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.scenario_history, f, indent=2)
        print(f"[ENV] Exported scenario history to {filepath}")

    def debug_check(self):
        """
        Verify the simulation is healthy without running the agent.

        Checks (in order):
          1. Grid topology counts match expected DC grid numbers.
          2. Power flow converges.
          3. No voltage violations on any bus.
          4. No transformer overloads.
          5. Transmission line loading summary.
          6. Top-5 most loaded buses (by p_mw draw).

        Safe to call after build_grid(); does NOT require initialize().
        """
        if self.grid is None:
            print("[DEBUG] Grid not built — call build_grid() first.")
            return

        net = self.grid.net
        sep = "─" * 60

        print(f"\n{sep}")
        print(f"  DEBUG CHECK — {self.grid.name}")
        print(sep)

        # ── 1. Topology counts ────────────────────────────────────────────────
        n_tx   = len(net.bus[net.bus["vn_kv"] == 115.0])
        n_dist = len(net.bus[net.bus["vn_kv"] == 13.8])
        print(f"\n[1] Topology")
        print(f"    Buses        : {len(net.bus):>3}  (tx={n_tx}, dist={n_dist})  expected 58")
        print(f"    TX lines     : {len(net.line):>3}  expected 10")
        print(f"    Transformers : {len(net.trafo):>3}  expected 51")
        print(f"    Generators   : {len(net.gen):>3}  expected 3")
        print(f"    Static loads : {len(net.load):>3}  expected 51")
        print(f"    DER (sgen)   : {len(net.sgen):>3}  expected 6  ({net.sgen['p_mw'].sum():.0f} MW)")

        ok = (len(net.bus) == 58 and len(net.line) == 10 and
              len(net.trafo) == 51 and len(net.gen) == 3 and len(net.load) == 51)
        print(f"    {'✓ Counts correct' if ok else '✗ Count mismatch — check build_grid()'}")

        # ── 2. Power flow ─────────────────────────────────────────────────────
        print(f"\n[2] Power Flow")
        try:
            import pandapower as pp
            pp.runpp(net, check_convergence=True, numba=False)
            print(f"    ✓ Converged")
        except Exception as exc:
            print(f"    ✗ FAILED: {exc}")
            print(sep)
            return

        # ── 3. Voltage check ──────────────────────────────────────────────────
        v_min_pu = self.grid.constraints["voltage_min_pu"]
        v_max_pu = self.grid.constraints["voltage_max_pu"]
        voltages  = net.res_bus["vm_pu"]
        low_buses  = net.bus[voltages < v_min_pu]["name"].tolist()
        high_buses = net.bus[voltages > v_max_pu]["name"].tolist()

        print(f"\n[3] Voltage  (limits: {v_min_pu}–{v_max_pu} p.u.)")
        print(f"    Range : {voltages.min():.4f} – {voltages.max():.4f} p.u.")
        if low_buses:
            print(f"    ✗ Under-voltage buses : {low_buses}")
        elif high_buses:
            print(f"    ✗ Over-voltage buses  : {high_buses}")
        else:
            print(f"    ✓ All buses within limits")

        # ── 4. Transformer loading ────────────────────────────────────────────
        print(f"\n[4] Transformer Loading")
        if net.trafo.empty or net.res_trafo.empty:
            print(f"    (no transformers)")
        else:
            t_loading = net.res_trafo["loading_percent"]
            overloaded = net.trafo[t_loading > 100]["name"].tolist()
            print(f"    Max loading : {t_loading.max():.1f}%  (mean {t_loading.mean():.1f}%)")
            if overloaded:
                print(f"    ✗ Overloaded transformers : {overloaded}")
            else:
                print(f"    ✓ No transformer overloads")

        # ── 5. Transmission line loading ─────────────────────────────────────
        print(f"\n[5] Transmission Line Loading")
        if net.line.empty or net.res_line.empty:
            print(f"    (no lines)")
        else:
            l_loading = net.res_line["loading_percent"]
            print(f"    Max loading : {l_loading.max():.1f}%  (mean {l_loading.mean():.1f}%)")
            for idx in l_loading.nlargest(3).index:
                name = net.line.loc[idx, "name"]
                pct  = net.res_line.loc[idx, "loading_percent"]
                print(f"    {name:<35} {pct:>6.1f}%")

        # ── 6. Top-5 loaded buses ─────────────────────────────────────────────
        print(f"\n[6] Top-5 Buses by Load Draw (MW)")
        bus_p = net.res_bus["p_mw"].abs()
        for idx in bus_p.nlargest(5).index:
            bname = net.bus.loc[idx, "name"]
            p_mw  = net.res_bus.loc[idx, "p_mw"]
            v_pu  = net.res_bus.loc[idx, "vm_pu"]
            print(f"    {bname:<25} {p_mw:>8.1f} MW   {v_pu:.4f} p.u.")

        print(f"\n{sep}\n")


# ============================================================================
# EXAMPLE: How to use the SimulationEnvironment
# ============================================================================

def example_usage():
    """
    Example workflow: build grid, run power flow, run agent scenario.
    """
    print("\n" + "="*70)
    print("EXAMPLE: Grid Simulation Workflow")
    print("="*70)
    
    # Create environment
    env = SimulationEnvironment()
    
    # Build grid (uses placeholder 3-bus grid)
    env.build_grid()
    
    # Initialize (compile power flow engine, agent)
    env.initialize()
    
    # Run scenario for 24 hours
    results = env.run_scenario(steps=24, apply_agent=True, print_reports=False)
    
    # Print summary
    summary = env.get_scenario_summary()
    print("\nScenario Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Export to JSON (for dashboard/analysis)
    env.export_history_json('/tmp/scenario_history.json')
    
    print("\n" + "="*70)


if __name__ == "__main__":
    env = SimulationEnvironment()
    env.build_grid()
    env.debug_check()