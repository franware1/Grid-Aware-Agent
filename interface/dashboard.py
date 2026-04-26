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

from run_live import run as run_live_sim

SPIKES_PATH = ROOT / "data" / "spikes.csv"

st.set_page_config(page_title="GridAgent — DOM Zone Monitor", layout="wide")
st.title("GridAgent — PJM Dominion (Northern Virginia) Load Monitor")

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Simulation controls")
n_ticks = st.sidebar.slider("Ticks to simulate (1 tick = 10 min)", 36, 576, 144)
run_btn = st.sidebar.button("Run simulation", type="primary")

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
    st.subheader("Pepco DC grid — live simulation")
    st.caption(
        "Runs the 58-bus Pepco DC grid with a 24-hour demand profile and demo events. "
        "Brain 1 scores grid risk each tick; Brain 2 recommends operator actions."
    )

    if run_btn:
        with st.spinner(f"Running {n_ticks} ticks..."):
            log_buf = io.StringIO()
            with contextlib.redirect_stdout(log_buf):
                records = run_live_sim(ticks=n_ticks)
        st.session_state["sim_results"] = records
        st.session_state["sim_log"]     = log_buf.getvalue()

    if "sim_results" not in st.session_state:
        st.info("Configure parameters in the sidebar and click **Run simulation**.")
    else:
        results = pd.DataFrame(st.session_state["sim_results"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ticks run", len(results))
        c2.metric("Converged", f"{results['converged'].sum()} / {len(results)}")
        c3.metric("Max line loading", f"{results['line_loading_pct'].max():.0f}%")
        c4.metric("Min reserve", f"{results['reserve_mw'].min():.0f} MW")

        st.subheader("Line loading % per tick")
        st.line_chart(
            results.set_index("hour")[["line_loading_pct"]].rename(
                columns={"line_loading_pct": "Line loading (%)"}
            )
        )

        st.subheader("Reserve margin MW per tick")
        st.line_chart(
            results.set_index("hour")[["reserve_mw"]].rename(
                columns={"reserve_mw": "Reserve (MW)"}
            )
        )

        st.subheader("Overall risk score per tick")
        st.line_chart(
            results.set_index("hour")[["overall_risk"]].rename(
                columns={"overall_risk": "Risk (0–1)"}
            )
        )

        action_counts = results[results["brain2_action"] != ""]["brain2_action"].value_counts().reset_index()
        action_counts.columns = ["Action", "Count"]
        if not action_counts.empty:
            st.subheader("Brain 2 recommended actions")
            st.bar_chart(action_counts.set_index("Action"))

        st.subheader("Step-by-step results")
        st.dataframe(
            results[[
                "tick", "hour", "load_multiplier", "total_load_mw",
                "line_loading_pct", "reserve_mw", "overall_risk",
                "brain2_action", "brain2_target", "brain2_confidence",
                "n_violations", "converged", "active_events",
            ]].rename(columns={
                "tick":              "Tick",
                "hour":              "Hour",
                "load_multiplier":   "Load ×",
                "total_load_mw":     "Load MW",
                "line_loading_pct":  "Line loading %",
                "reserve_mw":        "Reserve MW",
                "overall_risk":      "Risk score",
                "brain2_action":     "Brain 2 action",
                "brain2_target":     "Target",
                "brain2_confidence": "Confidence",
                "n_violations":      "Violations",
                "converged":         "Converged",
                "active_events":     "Active events",
            }),
            use_container_width=True,
        )

        with st.expander("Simulation log"):
            st.code(st.session_state["sim_log"])
