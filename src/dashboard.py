"""
Streamlit dashboard for GridAgent.

Run with:
    streamlit run src/dashboard.py
"""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from run_simulation import run as run_simulation

SPIKES_PATH = ROOT / "data" / "spikes.csv"

st.set_page_config(page_title="GridAgent — DOM Zone Monitor", layout="wide")
st.title("GridAgent — PJM Dominion (Northern Virginia) Load Monitor")

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Simulation controls")
n_steps    = st.sidebar.slider("Spike intervals to simulate", 5, 100, 20)
top_spikes = st.sidebar.checkbox("Worst spikes first", value=True)
run_btn    = st.sidebar.button("Run simulation", type="primary")

# ── Tab layout ─────────────────────────────────────────────────────────────
tab_data, tab_sim = st.tabs(["Real data", "Simulation"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — Real spike data
# ═══════════════════════════════════════════════════════════════════════════
with tab_data:
    if not SPIKES_PATH.exists():
        st.warning(
            "No spike data found. Run `python src/baseline.py` first to generate `data/spikes.csv`."
        )
    else:
        spikes = pd.read_csv(SPIKES_PATH, parse_dates=["interval_start_utc"])
        spikes = spikes.sort_values("interval_start_utc")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Spike intervals (12 mo)", f"{len(spikes):,}")
        c2.metric("Avg spike ratio", f"{spikes['ratio'].mean():.2f}×")
        c3.metric("Worst spike", f"{spikes['ratio'].max():.2f}×")
        c4.metric(
            "Worst event",
            str(spikes.loc[spikes["ratio"].idxmax(), "interval_start_utc"])[:13],
        )

        st.subheader("DOM zone load vs. baseline — flagged spike intervals")
        mw_col = "actual_mw" if "actual_mw" in spikes.columns else "mw"
        chart_df = spikes.set_index("interval_start_utc")[[mw_col, "baseline_mw"]].rename(
            columns={mw_col: "Actual MW", "baseline_mw": "Baseline MW"}
        )
        st.line_chart(chart_df)

        st.subheader("Spike ratio over time")
        st.bar_chart(spikes.set_index("interval_start_utc")[["ratio"]])

        st.subheader("Top 20 worst spikes")
        st.dataframe(
            spikes.nlargest(20, "ratio")[
                ["interval_start_utc", "mw", "baseline_mw", "ratio"]
            ].rename(columns={
                "interval_start_utc": "Timestamp (UTC)",
                "mw": "Actual MW",
                "baseline_mw": "Baseline MW",
                "ratio": "Ratio",
            }).reset_index(drop=True),
            use_container_width=True,
        )

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — Simulation
# ═══════════════════════════════════════════════════════════════════════════
with tab_sim:
    st.subheader("pandapower grid simulation — DOM zone spike replay")
    st.caption(
        "Each spike interval from real GridStatus data is injected as a LOAD_SPIKE "
        "event on the DC_Tyson flexible load. The agent responds each step."
    )

    if not SPIKES_PATH.exists():
        st.warning("Run `python src/baseline.py` first.")
    else:
        # Run simulation and store results in session_state so they survive re-renders
        if run_btn:
            with st.spinner(f"Running {n_steps} simulation steps..."):
                log_buf = io.StringIO()
                with contextlib.redirect_stdout(log_buf):
                    records = run_simulation(steps=n_steps, top_spikes=top_spikes)
            st.session_state["sim_results"] = records
            st.session_state["sim_log"]     = log_buf.getvalue()

        if "sim_results" not in st.session_state:
            st.info("Configure parameters in the sidebar and click **Run simulation**.")
        else:
            results = pd.DataFrame(st.session_state["sim_results"])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Steps run", len(results))
            c2.metric("Converged", f"{results['converged'].sum()} / {len(results)}")
            c3.metric("Max line loading", f"{results['line_loading_pct'].max():.0f}%")
            c4.metric("Min reserve", f"{results['reserve_mw'].min():.0f} MW")

            st.subheader("Line loading % per step")
            st.line_chart(
                results.set_index("timestamp")[["line_loading_pct"]].rename(
                    columns={"line_loading_pct": "Line loading (%)"}
                )
            )

            st.subheader("Reserve margin MW per step")
            st.line_chart(
                results.set_index("timestamp")[["reserve_mw"]].rename(
                    columns={"reserve_mw": "Reserve (MW)"}
                )
            )

            action_counts = results["agent_action"].value_counts().reset_index()
            action_counts.columns = ["Action", "Count"]
            st.subheader("Agent actions")
            st.bar_chart(action_counts.set_index("Action"))

            st.subheader("Step-by-step results")
            st.dataframe(
                results[[
                    "timestamp", "ratio", "real_delta_mw",
                    "line_loading_pct", "reserve_mw",
                    "agent_action", "n_violations", "converged",
                ]].rename(columns={
                    "timestamp":        "Timestamp (UTC)",
                    "ratio":            "Spike ratio",
                    "real_delta_mw":    "Δ MW (real)",
                    "line_loading_pct": "Line loading %",
                    "reserve_mw":       "Reserve MW",
                    "agent_action":     "Agent action",
                    "n_violations":     "Violations",
                    "converged":        "Converged",
                }),
                use_container_width=True,
            )

            with st.expander("Simulation log"):
                st.code(st.session_state["sim_log"])
