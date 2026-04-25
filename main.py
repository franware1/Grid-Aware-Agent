from grid_simulation import create_grid, run_simulation, increase_data_center_demand
from brain1 import get_brain1_output

net, dc_load = create_grid()

print("=== NORMAL ===")
data = run_simulation(net)
print(get_brain1_output(data))

print("\n=== EVENT ===")
increase_data_center_demand(net, dc_load, 80)
data = run_simulation(net)
print(get_brain1_output(data))