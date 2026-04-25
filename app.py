import streamlit as st
from grid_simulation import create_grid, run_simulation, increase_data_center_demand
from brain1 import get_brain1_output
import pandas as pd

st.title("Grid Status Dashboard")
st.caption("AI Grid Advisor — Hackathon Demo")

# Create grid
net, dc_load = create_grid()

# Event toggle
event = st.checkbox("Simulate Data Center Demand Increase")

if event:
    increase_data_center_demand(net, dc_load, 80)

# Run simulation
grid_data = run_simulation(net)

# Brain 1
brain1_output = get_brain1_output(grid_data)
risk_score = brain1_output["risk_score"]
risk_level = brain1_output["risk_level"]

st.success("System Running")

# Risk display
col1, col2 = st.columns(2)

with col1:
    st.subheader("Risk Level")
    if risk_level == "HIGH":
        st.error("HIGH")
    elif risk_level == "MEDIUM":
        st.warning("MEDIUM")
    else:
        st.success("LOW")

with col2:
    st.subheader("Risk Score")
    st.metric("Score", risk_score)

st.divider()

# Explanation (temporary until Brain 2)
st.subheader("Explanation")
if risk_level == "HIGH":
    st.info("The grid is under stress due to increased demand and voltage drop.")
elif risk_level == "MEDIUM":
    st.info("The grid is showing moderate stress.")
else:
    st.info("The grid is operating normally.")

# Recommendation
st.subheader("Recommended Action")
if risk_level == "HIGH":
    st.warning("Reduce non-critical load or redistribute power.")
elif risk_level == "MEDIUM":
    st.warning("Monitor system and prepare corrective actions.")
else:
    st.success("No action needed.")

st.divider()

# Grid metrics
st.subheader("Grid Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Line Loading (%)", round(grid_data["max_line_loading"], 2))

with col2:
    st.metric("Voltage (pu)", round(grid_data["min_voltage"], 3))

with col3:
    st.metric("Total Load (MW)", round(grid_data["total_load"], 2))

st.divider()

# Chart
data = pd.DataFrame({
    "Metric": ["Line Loading", "Voltage", "Total Load"],
    "Value": [
        grid_data["max_line_loading"],
        grid_data["min_voltage"] * 100,
        grid_data["total_load"]
    ]
})

st.subheader("System Metrics")
st.bar_chart(data.set_index("Metric"))