"""
Streamlit dashboard for GridAgent.

Run with:
    streamlit run interface/dashboard.py
"""

import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

LIVE_LOG_PATH = ROOT / "data" / "live_log.csv"
SPIKES_PATH   = ROOT / "data" / "spikes.csv"

st.set_page_config(page_title="GridAgent — DC Grid Monitor", layout="wide")
st.title("GridAgent — Pepco DC Grid Monitor")

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.header("Controls")
auto_refresh = st.sidebar.checkbox("Auto-refresh live log (5 s)", value=False)
st.sidebar.button("Refresh now", key="refresh_btn")

# ── Tabs ───────────────────────────────────────────────────────────────────
tab_live, tab_sim, tab_data = st.tabs(["Live Log", "Run Simulation", "Real Spike Data"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — Live log written by run_live.py
# ═══════════════════════════════════════════════════════════════════════════
with tab_live:
    st.subheader("Live simulation log")
    st.caption(
        f"Reads `data/live_log.csv` written by `run_live.py`. "
        "Start the simulation in a terminal, then refresh here to see updates."
    )

    if not LIVE_LOG_PATH.exists() or LIVE_LOG_PATH.stat().st_size == 0:
        st.info(
            "No live log found yet.  \n"
            "Run `python src/run_live.py` in a terminal to start recording."
        )
    else:
        df = pd.read_csv(LIVE_LOG_PATH)

        # ── Summary metrics ───────────────────────────────────────────────
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ticks recorded", len(df))
        c2.metric("Days simulated", int(df["day"].max()) if "day" in df.columns else "—")
        c3.metric("Max line loading", f"{df['max_line_loading_pct'].max():.1f}%")
        c4.metric("Min reserve", f"{df['reserve_mw'].min():.0f} MW")
        c5.metric("Events fired", int(df["event_fired"].sum()))

        # ── DC_NoMa load ──────────────────────────────────────────────────
        st.subheader("DC_NoMa flexible load (MW)")
        st.line_chart(df.set_index("tick")[["dc_noma_mw"]])

        # ── Grid health ───────────────────────────────────────────────────
        st.subheader("Grid health")
        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("Max line loading %")
            st.line_chart(df.set_index("tick")[["max_line_loading_pct"]])
        with col_b:
            st.caption("Reserve margin (MW)")
            st.line_chart(df.set_index("tick")[["reserve_mw"]])

        # ── Brain 1 risk ──────────────────────────────────────────────────
        st.subheader("Brain 1 — risk score over time")
        st.line_chart(df.set_index("tick")[["brain1_risk"]])

        # ── Brain 2 actions ───────────────────────────────────────────────
        b2_rows = df[df["brain2_triggered"] == 1]
        if not b2_rows.empty:
            st.subheader("Brain 2 — recommended actions")
            action_counts = (
                b2_rows["brain2_action"]
                .value_counts()
                .reset_index()
            )
            action_counts.columns = ["Action", "Count"]
            st.bar_chart(action_counts.set_index("Action"))

        # ── Event timeline ────────────────────────────────────────────────
        events = df[df["event_fired"] == 1][
            ["tick", "sim_time", "day", "event_name", "event_type", "operator_choice"]
        ]
        if not events.empty:
            st.subheader("Event timeline")
            st.dataframe(
                events.rename(columns={
                    "tick":           "Tick",
                    "sim_time":       "Time",
                    "day":            "Day",
                    "event_name":     "Event",
                    "event_type":     "Type",
                    "operator_choice":"Operator response",
                }),
                use_container_width=True,
            )

        # ── Full log ──────────────────────────────────────────────────────
        with st.expander("Full tick log"):
            st.dataframe(df, use_container_width=True)

        st.caption(f"Last refreshed: {pd.Timestamp.now().strftime('%H:%M:%S')}")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — On-demand simulation (no operator prompts, Brain 2 advisory only)
# ═══════════════════════════════════════════════════════════════════════════
with tab_sim:
    st.subheader("On-demand simulation")
    st.caption(
        "Runs the 58-bus Pepco DC grid for N ticks with Brain 1 + Brain 2. "
        "Events auto-expire (no operator prompts). 1 tick = 30 min simulated."
    )

    n_ticks = st.slider("Ticks to simulate (1 tick = 30 min)", 16, 336, 48)
    run_btn = st.button("Run simulation", type="primary")

    if run_btn:
        try:
            from run_live import run as _run
            with st.spinner(f"Running {n_ticks} ticks…"):
                records = _run(ticks=n_ticks)
            st.session_state["sim_results"] = records
            st.session_state["sim_error"]   = None
        except Exception as exc:
            st.session_state["sim_error"] = str(exc)

    if st.session_state.get("sim_error"):
        st.error(f"Simulation error: {st.session_state['sim_error']}")

    elif "sim_results" not in st.session_state:
        st.info("Click **Run simulation** to start.")

    else:
        results = pd.DataFrame(st.session_state["sim_results"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ticks run",        len(results))
        c2.metric("Converged",         f"{results['converged'].sum()} / {len(results)}")
        c3.metric("Max line loading",  f"{results['line_loading_pct'].max():.0f}%")
        c4.metric("Min reserve",       f"{results['reserve_mw'].min():.0f} MW")

        st.subheader("Line loading % per tick")
        st.line_chart(
            results.set_index("tick")[["line_loading_pct"]].rename(
                columns={"line_loading_pct": "Line loading (%)"}
            )
        )

        st.subheader("Reserve margin MW")
        st.line_chart(
            results.set_index("tick")[["reserve_mw"]].rename(
                columns={"reserve_mw": "Reserve (MW)"}
            )
        )

        st.subheader("Brain 1 — risk score")
        st.line_chart(
            results.set_index("tick")[["overall_risk"]].rename(
                columns={"overall_risk": "Risk (0–1)"}
            )
        )

        b2_rows = results[results["brain2_action"] != ""]
        if not b2_rows.empty:
            st.subheader("Brain 2 — recommended actions")
            action_counts = b2_rows["brain2_action"].value_counts().reset_index()
            action_counts.columns = ["Action", "Count"]
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
                "hour":              "Time",
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

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — Real PJM DOM zone spike data
# ═══════════════════════════════════════════════════════════════════════════
with tab_data:
    if not SPIKES_PATH.exists():
        st.warning(
            "No spike data found.  \n"
            "Run `python interface/baseline.py` to generate `data/spikes.csv`."
        )
    else:
        spikes = pd.read_csv(SPIKES_PATH, parse_dates=["interval_start_utc"])
        spikes = spikes.sort_values("interval_start_utc")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Spike intervals (12 mo)", f"{len(spikes):,}")
        c2.metric("Avg spike ratio",         f"{spikes['ratio'].mean():.2f}×")
        c3.metric("Worst spike",             f"{spikes['ratio'].max():.2f}×")
        c4.metric(
            "Worst event",
            str(spikes.loc[spikes["ratio"].idxmax(), "interval_start_utc"])[:13],
        )

        mw_col = "actual_mw" if "actual_mw" in spikes.columns else "mw"
        st.subheader("DOM zone load vs. baseline — flagged spike intervals")
        st.line_chart(
            spikes.set_index("interval_start_utc")[[mw_col, "baseline_mw"]].rename(
                columns={mw_col: "Actual MW", "baseline_mw": "Baseline MW"}
            )
        )

        st.subheader("Spike ratio over time")
        st.bar_chart(spikes.set_index("interval_start_utc")[["ratio"]])

        st.subheader("Top 20 worst spikes")
        st.dataframe(
            spikes.nlargest(20, "ratio")[
                ["interval_start_utc", "mw", "baseline_mw", "ratio"]
            ].rename(columns={
                "interval_start_utc": "Timestamp (UTC)",
                "mw":                 "Actual MW",
                "baseline_mw":        "Baseline MW",
                "ratio":              "Ratio",
            }).reset_index(drop=True),
            use_container_width=True,
        )

# ── Auto-refresh (runs after all tabs render) ───────────────────────────────
if auto_refresh:
    time.sleep(5)
    st.rerun()
