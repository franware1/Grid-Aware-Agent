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
from simulator.network import GridNetwork
from simulator.power_flow import PowerFlowEngine
from simulator.agent import GridOptimizationAgent
import json


class SimulationEnvironment:
    """
    Main simulation environment: orchestrates grid, power flow, and agent.
    """
    
    def __init__(self, grid_name: str = "My Grid"):
        """Initialize the simulation environment."""
        self.grid_name = grid_name
        self.grid: Optional[GridNetwork] = None
        self.pf_engine: Optional[PowerFlowEngine] = None
        self.agent: Optional[GridOptimizationAgent] = None
        
        self.scenario_history: List[Dict] = []
        self.current_time_step = 0
    
    def build_grid(self):
        """
        Create and populate the grid.
        OVERRIDE THIS with your actual grid definition.
        
        This is a placeholder that creates a minimal 3-bus test case.
        """
        from simulator.network import (
            BusSpec, LineSpec, GeneratorSpec, LoadSpec,
            FlexibleLoadSpec, StaticGeneratorSpec
        )
        
        self.grid = GridNetwork(name=self.grid_name)
        
        # --- BUSES ---
        self.grid.add_bus(BusSpec(name="Bus_Gen", vn_kv=345.0, bus_type="n"))  # Slack
        self.grid.add_bus(BusSpec(name="Bus_Central", vn_kv=345.0, bus_type="b"))
        self.grid.add_bus(BusSpec(name="Bus_Load", vn_kv=110.0, bus_type="b"))
        
        # --- LINES ---
        self.grid.add_line(LineSpec(
            name="Line_Gen_Central",
            from_bus="Bus_Gen",
            to_bus="Bus_Central",
            length_km=50.0,
            r_ohm_per_km=0.03,
            x_ohm_per_km=0.35,
            c_nf_per_km=10.0,
            sn_mva=500.0,
        ))
        
        self.grid.add_line(LineSpec(
            name="Line_Central_Load",
            from_bus="Bus_Central",
            to_bus="Bus_Load",
            length_km=30.0,
            r_ohm_per_km=0.05,
            x_ohm_per_km=0.40,
            c_nf_per_km=8.0,
            sn_mva=250.0,
        ))
        
        # --- GENERATOR (slack bus) ---
        self.grid.add_generator(GeneratorSpec(
            name="Gen_Coal",
            bus="Bus_Gen",
            p_mw=500.0,
            q_mvar=0.0,
            slack=True,
        ))
        
        # --- LOADS (static) ---
        self.grid.add_load(LoadSpec(
            name="Load_City",
            bus="Bus_Load",
            p_mw=200.0,
            q_mvar=50.0,
        ))
        
        # --- FLEXIBLE LOAD (data center) ---
        flex_load_spec = FlexibleLoadSpec(
            name="DC_Tyson",
            bus="Bus_Load",
            baseline_mw=100.0,
            min_mw=50.0,
            max_mw=150.0,
            deferrable_pct=0.25,
            defer_window_hours=4,
        )
        self.flex_load = self.grid.add_flexible_load(flex_load_spec)
        
        # --- STATIC GENERATOR (renewable) ---
        self.grid.add_static_gen(StaticGeneratorSpec(
            name="Solar_Farm",
            bus="Bus_Load",
            p_mw=50.0,
            q_mvar=0.0,
        ))
        
        print(f"[ENV] Grid '{self.grid_name}' built:")
        print(f"      {len(self.grid.net.bus)} buses")
        print(f"      {len(self.grid.net.line)} lines")
        print(f"      {len(self.grid.net.gen)} generators")
        print(f"      {len(self.grid.net.load)} static loads")
    
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
            flex_loads = {'DC_Tyson': self.flex_load}  # Hardcoded for now
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
    env = SimulationEnvironment(grid_name="Test Grid")
    
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
    print("[BOILERPLATE] Integration Module Loaded")
    print("Use SimulationEnvironment to orchestrate grid + power flow + agent.")
    
    # Uncomment to run example:
    # example_usage()