"""
GridAgent — Live Operations Dashboard
Run: streamlit run api/dashboard.py
"""

import math, time, random
from datetime import datetime
import streamlit as st
import pandas as pd

st.set_page_config(page_title="GridAgent // Pepco DC", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap');
html,body,[data-testid="stApp"]{background:#060a0f!important;color:#a8c8a0!important;font-family:'Rajdhani',sans-serif!important;}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important;}
.main .block-container{padding:0!important;max-width:100%!important;}

.ems-header{background:#0a1a0e;border-bottom:1px solid #1a4a22;padding:10px 24px;display:flex;align-items:center;justify-content:space-between;}
.ems-logo{font-family:'Share Tech Mono';font-size:13px;color:#2ecc71;letter-spacing:.15em;text-transform:uppercase;}
.ems-logo span{color:#7fff7f;}
.ems-clock{font-family:'Share Tech Mono';font-size:24px;color:#c8f0c0;letter-spacing:.1em;}
.ems-sub{font-family:'Share Tech Mono';font-size:9px;color:#2a5a2a;letter-spacing:.1em;margin-top:2px;}

.kpi-strip{background:#080e10;border-bottom:1px solid #112211;padding:0 12px;display:flex;}
.kpi-block{flex:1;padding:10px 14px;border-right:1px solid #0d1e0d;}
.kpi-block:last-child{border-right:none;}
.kpi-label{font-family:'Share Tech Mono';font-size:9px;color:#3a6a3a;letter-spacing:.12em;text-transform:uppercase;margin-bottom:3px;}
.kpi-value{font-family:'Share Tech Mono';font-size:26px;line-height:1;letter-spacing:.04em;}
.kpi-unit{font-family:'Share Tech Mono';font-size:9px;color:#3a6a3a;letter-spacing:.1em;margin-top:2px;}
.kpi-ok{color:#2ecc71;}.kpi-warn{color:#f0a030;}.kpi-crit{color:#e74c3c;}.kpi-info{color:#4ac8f0;}.kpi-dim{color:#7fff7f;}

.alarm-strip{background:#04090c;border-bottom:2px solid #1a1a00;padding:5px 16px;display:flex;gap:8px;align-items:center;min-height:34px;overflow-x:auto;}
.alarm-item{font-family:'Share Tech Mono';font-size:10px;padding:3px 8px;border-radius:2px;white-space:nowrap;letter-spacing:.06em;}
.alarm-crit{background:rgba(231,76,60,.15);border:1px solid #e74c3c;color:#ff6b6b;animation:blink 1.2s infinite;}
.alarm-warn{background:rgba(240,160,48,.12);border:1px solid #f0a030;color:#ffc060;}
.alarm-ok{background:rgba(46,204,113,.08);border:1px solid #1a6a2a;color:#2ecc71;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.45}}
.alarm-ts{font-family:'Share Tech Mono';font-size:9px;color:#2a5a2a;margin-left:auto;}

.scada-card{background:#080e10;border:1px solid #112211;border-top:2px solid #1a4a22;padding:12px 16px;}
.scada-card-title{font-family:'Share Tech Mono';font-size:9px;color:#2a5a2a;letter-spacing:.18em;text-transform:uppercase;margin-bottom:10px;border-bottom:1px solid #0a1e0a;padding-bottom:6px;}
.oneline-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #0a1a0a;font-family:'Share Tech Mono';font-size:11px;}
.oneline-row:last-child{border-bottom:none;}
.oneline-name{color:#5a9a5a;font-size:10px;}
.oneline-val{color:#c8f0c0;}
.oneline-status{font-size:9px;padding:2px 6px;border-radius:1px;}
.st-ok{background:rgba(46,204,113,.1);color:#2ecc71;border:1px solid #1a5a1a;}
.st-warn{background:rgba(240,160,48,.1);color:#f0a030;border:1px solid #6a4a10;}
.st-crit{background:rgba(231,76,60,.1);color:#e74c3c;border:1px solid #6a1a1a;}

.risk-big{font-family:'Share Tech Mono';font-size:48px;line-height:1;letter-spacing:.04em;}
.risk-bar-wrap{height:6px;background:#0d1f0d;border-radius:3px;margin:8px 0;overflow:hidden;}
.risk-bar{height:100%;border-radius:3px;}

.b2-box{background:rgba(42,122,170,.08);border:1px solid #1a4a6a;border-left:3px solid #2a7aaa;padding:12px 14px;margin:6px 0;border-radius:2px;}
.plain-box{background:rgba(46,204,113,.04);border:1px solid #1a4a22;border-left:3px solid #2ecc71;padding:10px 14px;border-radius:2px;margin-top:8px;}
.plain-title{font-family:'Share Tech Mono';font-size:9px;color:#2ecc71;letter-spacing:.15em;text-transform:uppercase;margin-bottom:4px;}
.plain-text{font-family:'Rajdhani';font-size:13px;color:#a8d8a0;line-height:1.5;}

.evlog-row{display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-bottom:1px solid #0a150a;}
.evlog-tick{font-family:'Share Tech Mono';font-size:9px;color:#2a4a2a;min-width:52px;}
.evlog-dot{width:5px;height:5px;border-radius:50%;margin-top:4px;flex-shrink:0;}
.evlog-msg{font-family:'Share Tech Mono';font-size:10px;color:#6ab06a;line-height:1.4;}
.log-scroll{height:180px;overflow-y:auto;}
.log-scroll::-webkit-scrollbar{width:3px;}
.log-scroll::-webkit-scrollbar-thumb{background:#1a3a1a;border-radius:2px;}

/* === ACTION BUTTONS — context-sensitive highlighting === */
.stButton>button{
    background:#0a1e0a!important;border:1px solid #1a5a1a!important;
    color:#2ecc71!important;font-family:'Share Tech Mono'!important;
    font-size:11px!important;letter-spacing:.08em!important;
    border-radius:2px!important;padding:6px 18px!important;width:100%;
    transition:all .2s;
}
.stButton>button:hover{background:#0d2e0d!important;border-color:#2ecc71!important;}

/* Highlighted "DO THIS NOW" button */
.btn-highlight>div>button{
    background:rgba(231,76,60,.18)!important;
    border:2px solid #e74c3c!important;
    color:#ff8080!important;
    animation:btnpulse 1.5s infinite!important;
    font-size:12px!important;
}
@keyframes btnpulse{0%,100%{box-shadow:0 0 0 0 rgba(231,76,60,.4)}50%{box-shadow:0 0 12px 4px rgba(231,76,60,.25)}}

.btn-recommend>div>button{
    background:rgba(240,160,48,.12)!important;
    border:1px solid #f0a030!important;
    color:#ffc060!important;
}

[data-testid="stSelectbox"] label,[data-testid="stSlider"] label{font-family:'Share Tech Mono'!important;font-size:10px!important;color:#2a5a2a!important;letter-spacing:.1em!important;}
[data-testid="stSelectbox"]>div>div{background:#080e10!important;border:1px solid #1a4a1a!important;border-radius:2px!important;color:#a8c8a0!important;font-family:'Share Tech Mono'!important;font-size:11px!important;}
[data-testid="stTabs"] [role="tab"]{font-family:'Share Tech Mono'!important;font-size:10px!important;letter-spacing:.12em!important;color:#3a6a3a!important;background:transparent!important;border-bottom:2px solid transparent!important;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{color:#2ecc71!important;border-bottom:2px solid #2ecc71!important;}
[data-testid="stTabs"] [role="tablist"]{background:#060a0f!important;border-bottom:1px solid #112211!important;}
[data-testid="stTab"]{background:#060a0f!important;padding:0!important;}
div[data-testid="column"]{padding:4px 6px!important;}
[data-testid="stVerticalBlock"]{gap:.4rem!important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# EXACT EVENTS FROM run_live.py  (tick = scheduled_at, 1 tick = 10 min)
# ══════════════════════════════════════════════════════════════
TICKS_PER_DAY = 144
HOURLY = [0.81,0.80,0.79,0.78,0.77,0.78,0.81,0.88,0.95,
          1.00,1.02,1.03,1.03,1.04,1.05,1.07,1.10,1.13,
          1.15,1.16,1.14,1.09,1.00,0.90]
LOAD_PROFILE = [round(HOURLY[i//6]+(i%6)/6*(HOURLY[(i//6+1)%24]-HOURLY[i//6]),4) for i in range(TICKS_PER_DAY)]
BASE_LOAD_MW = 1182.0
BASE_GEN_MAX = 2050.0
DC_BASELINE  = 110.0

# Mirrored exactly from DEMO_SCHEDULE in run_live.py
DEMO_EVENTS = [
    dict(tick=36,  etype="AI_TRAINING_SPIKE",   dur=24, p=dict(min_mw=25.0, max_mw=60.0),
         name="Morning Training Job",
         plain="A large AI model training job just launched at the NoMa data center. It's pulling significantly more power than normal — like hundreds of extra computers all turning on at once."),
    dict(tick=84,  etype="AI_TRAINING_DROPOUT", dur=18, p=dict(dropout=0.75),
         name="Training Job Crash",
         plain="The AI training job crashed mid-run. Power demand dropped by 75% almost instantly. Sudden drops like this can be just as destabilizing as sudden spikes."),
    dict(tick=108, etype="COOLING_CASCADE",      dur=36, p=dict(comp=40.0, cool=18.0, delay=3),
         name="Cooling Cascade",
         plain="The data center's computers ran hot, so the cooling systems kicked in. First the compute load spiked, and 30 minutes later the chillers added even more demand — a double wave."),
    dict(tick=180, etype="LOAD_OSCILLATION",     dur=48, p=dict(amp=15.0, period=4.0),
         name="Load Oscillation",
         plain="The data center's power electronics are causing its draw to swing up and down in a rhythm. This makes it difficult for the grid to stay in balance."),
]

TX_LINES = ["Benning→EastCapitol","EastCapitol→Greenway","Greenway→HainsPoint",
            "HainsPoint→Buzzard","Buzzard→Georgetown","Georgetown→Nevada",
            "Nevada→Benning","Benning→Georgetown","Nevada→HainsPoint","EastCapitol→Buzzard"]
BASE_LINE_PCT = [12.1,9.8,8.3,9.1,11.4,13.7,17.8,21.3,15.6,10.9]

ACTION_PLAIN = {
    "CURTAIL_LOAD":    ("Reduce data center power now",    "Ask the data center to temporarily dial back. Like turning down AC during a heat wave to keep the lights on for everyone."),
    "DEFER_WORKLOAD":  ("Delay non-urgent computing tasks", "Ask the data center to pause background jobs and run them tonight when the grid has more breathing room."),
    "NO_ACTION":       ("No action needed",                 "The grid is stable. Everything is within safe limits."),
    "RESTORE_BASELINE":("Return to normal operations",      "The stress has passed. The data center can go back to its normal operating level."),
    "ALERT_OPERATOR":  ("Get a human to review",            "The situation is complex enough that a person should assess it before any automated action is taken."),
}

DC_STATE_PLAIN = {
    "NOMINAL":          "Running normally.",
    "TRAINING SPIKE":   "Running a major AI training job — power demand is well above normal.",
    "TRAINING DROPOUT": "A training job just crashed — demand dropped sharply and unexpectedly.",
    "COOLING CASCADE":  "Compute and cooling systems are both surging — a double demand wave.",
    "OSCILLATING":      "Power draw is swinging up and down rhythmically — hard for the grid to track.",
}

def tick_to_time(t):
    dt = t % TICKS_PER_DAY
    return f"{dt//6:02d}:{(dt%6)*10:02d}"

def compute_step(tick, events, manual_mw=0.0):
    mult = LOAD_PROFILE[tick % TICKS_PER_DAY]
    dc_extra = manual_mw
    dc_state = "NOMINAL"
    active_ev = []

    for ev in events:
        if ev["tick"] <= tick < ev["tick"] + ev["dur"]:
            age = tick - ev["tick"]
            active_ev.append(ev)
            et, p = ev["etype"], ev["p"]
            if et == "AI_TRAINING_SPIKE":
                if "_mag" not in ev:
                    ev["_mag"] = round(random.uniform(p["min_mw"], p["max_mw"]), 1)
                dc_extra += ev["_mag"]
                dc_state = "TRAINING SPIKE"
            elif et == "AI_TRAINING_DROPOUT":
                dc_extra -= DC_BASELINE * p["dropout"]
                dc_state = "TRAINING DROPOUT"
            elif et == "COOLING_CASCADE":
                dc_extra += p["comp"]
                if age >= p["delay"]: dc_extra += p["cool"]
                dc_state = "COOLING CASCADE"
            elif et == "LOAD_OSCILLATION":
                dc_extra += p["amp"] * math.sin(2*math.pi*age/p["period"])
                dc_state = "OSCILLATING"
        elif tick == ev["tick"] + ev["dur"]:
            ev.pop("_mag", None)

    dc_load    = max(80.0, min(140.0, DC_BASELINE + dc_extra))
    total_load = round(BASE_LOAD_MW * mult + (dc_load - DC_BASELINE), 1)
    reserve    = round(BASE_GEN_MAX - total_load, 1)
    stress     = max(0, dc_load-110)*0.38 + (mult-0.77)*195
    line_pcts  = [round(b+(stress if i in (6,8) else stress*0.3),1) for i,b in enumerate(BASE_LINE_PCT)]
    max_line   = max(line_pcts)
    v_min      = round(1.000-(mult-0.77)*0.012-max(0,dc_load-110)*0.0004, 4)
    v_max      = round(1.003, 4)

    b1_line = 0.90 if max_line>=90 else 0.65 if max_line>=85 else 0.35 if max_line>=75 else 0.10
    b1_res  = 0.90 if reserve<=300 else 0.50 if reserve<=400 else 0.10
    b1_volt = 0.90 if v_min<=0.95 else 0.40 if v_min<=0.97 else 0.05
    overall = round(max(b1_line, b1_res, b1_volt), 3)
    top_threat = max([("line",b1_line),("reserve",b1_res),("voltage",b1_volt)], key=lambda x:x[1])[0]

    violations = []
    if max_line > 100: violations.append(dict(name=TX_LINES[6], val=f"{max_line:.1f}%", sev="CRIT"))
    if reserve  < 350: violations.append(dict(name="Reserve Margin", val=f"{reserve:.0f} MW", sev="CRIT"))
    if v_min    < 0.97: violations.append(dict(name="Bus Voltage", val=f"{v_min:.4f} pu", sev="WARN"))

    # Brain 2 decision
    action_needed = overall >= 0.50
    if action_needed:
        if max_line >= 90:
            b2="CURTAIL_LOAD"; conf="HIGH"
            why=f"The Nevada→Benning transmission line is at {max_line:.0f}% of its limit. If it hits 100% it trips automatically, forcing power onto other lines — which can cascade. Curtailing the data center by 20% brings it back to a safe range immediately."
        elif reserve < 400:
            b2="DEFER_WORKLOAD"; conf="MEDIUM"
            why=f"The grid's safety buffer is down to {reserve:.0f} MW — below the 400 MW threshold operators prefer. Delaying the data center's background computing tasks would free up ~16 MW and restore comfortable headroom."
        else:
            b2="ALERT_OPERATOR"; conf="LOW"
            why=f"Risk score is {overall:.2f} — elevated but not severe enough for automatic action. A human operator should assess the trend before committing to a response."
        target="DC_NoMa data center"
    else:
        b2="NO_ACTION"; conf="HIGH"; target="—"
        why=f"Reserve is {reserve:.0f} MW. Max line loading is {max_line:.1f}%. Voltage is {v_min:.4f}–{v_max:.4f} pu. The grid is handling demand comfortably."

    return dict(
        tick=tick, time=tick_to_time(tick), mult=mult,
        total_load=total_load, reserve=reserve,
        dc_load=round(dc_load,1), dc_state=dc_state,
        max_line=max_line, line_pcts=line_pcts,
        v_min=v_min, v_max=v_max,
        overall_risk=overall, top_threat=top_threat,
        b1_line=b1_line, b1_res=b1_res, b1_volt=b1_volt,
        action_needed=action_needed,
        b2=b2, target=target, conf=conf, why=why,
        violations=violations, active_events=active_ev,
    )

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════
def _fresh(): return [dict(**e) for e in DEMO_EVENTS]

if "tick" not in st.session_state:
    st.session_state.tick = 0
    st.session_state.running = True
    st.session_state.events = _fresh()
    st.session_state.history = []
    st.session_state.agent_log = []
    st.session_state.runtime_log = []
    st.session_state.manual_mw = 0.0
    st.session_state.speed = "1 s"
    st.session_state.action_taken = {}   # tick -> action chosen

def reset():
    st.session_state.tick = 0
    st.session_state.running = True
    st.session_state.events = _fresh()
    st.session_state.history = []
    st.session_state.agent_log = []
    st.session_state.runtime_log = []
    st.session_state.manual_mw = 0.0
    st.session_state.action_taken = {}

def _rc(r): return "#e74c3c" if r>=0.65 else "#f0a030" if r>=0.35 else "#2ecc71"
def _kc(v,w,c,inv=False):
    if inv: return "kpi-crit" if v<=c else "kpi-warn" if v<=w else "kpi-ok"
    return "kpi-crit" if v>=c else "kpi-warn" if v>=w else "kpi-ok"
def _ac(a): return {"CURTAIL_LOAD":"#e74c3c","DEFER_WORKLOAD":"#f0a030","NO_ACTION":"#2ecc71","RESTORE_BASELINE":"#2ecc71","ALERT_OPERATOR":"#4ac8f0"}.get(a,"#a8c8a0")

# ══════════════════════════════════════════════════════════════
# ADVANCE TICK
# ══════════════════════════════════════════════════════════════
if st.session_state.running:
    st.session_state.tick += 1
    if st.session_state.tick >= 288:
        st.session_state.running = False

S = compute_step(st.session_state.tick, st.session_state.events, st.session_state.manual_mw)

# History
if not st.session_state.history or st.session_state.history[-1]["tick"] != S["tick"]:
    st.session_state.history.append({"tick":S["tick"],"time":S["time"],"load":S["total_load"],"reserve":S["reserve"],"line":S["max_line"],"risk":S["overall_risk"],"dc":S["dc_load"]})
    if len(st.session_state.history) > 288:
        st.session_state.history = st.session_state.history[-288:]

# Event fire/clear log
for ev in st.session_state.events:
    if ev["tick"] == S["tick"]:
        st.session_state.runtime_log.insert(0, dict(tick=S["tick"], time=S["time"], ev=ev, status="FIRED"))
    if ev["tick"]+ev["dur"]-1 == S["tick"]:
        st.session_state.runtime_log.insert(0, dict(tick=S["tick"], time=S["time"], ev=ev, status="CLEARED"))

# Agent log
if S["action_needed"] and S["b2"] != "NO_ACTION":
    if not st.session_state.agent_log or st.session_state.agent_log[0].get("tick") != S["tick"]:
        st.session_state.agent_log.insert(0, dict(tick=S["tick"], time=S["time"], action=S["b2"], target=S["target"], risk=S["overall_risk"]))
        if len(st.session_state.agent_log) > 60: st.session_state.agent_log.pop()

hist_df = pd.DataFrame(st.session_state.history) if st.session_state.history else pd.DataFrame()
now_str = datetime.now().strftime("%H:%M:%S")
day_num = S["tick"]//TICKS_PER_DAY + 1

# ── What's the current event context? ────────────────────────
current_event = S["active_events"][0] if S["active_events"] else None
needs_decision = S["action_needed"] and S["b2"] != "NO_ACTION"

# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
sys_label = ("⚠  ACTION NEEDED — SEE RECOMMENDED BUTTON BELOW" if needs_decision
             else "NORMAL — ALL SYSTEMS STABLE")
sys_color = "#e74c3c" if S["overall_risk"]>=0.65 else "#f0a030" if S["overall_risk"]>=0.35 else "#2ecc71"

st.markdown(f"""
<div class="ems-header">
  <div>
    <div class="ems-logo">⚡ GRIDAGENT // <span>PEPCO DC — LIVE GRID MONITOR</span></div>
    <div class="ems-sub">WASHINGTON DC · 58 SUBSTATIONS · NOMA DATA CENTER HUB · TICK {S['tick']:04d} / {TICKS_PER_DAY*2}</div>
  </div>
  <div style="text-align:center">
    <div style="font-family:'Share Tech Mono';font-size:12px;color:{sys_color};letter-spacing:.1em">{sys_label}</div>
  </div>
  <div style="text-align:right">
    <div class="ems-clock">{S['time']}</div>
    <div class="ems-sub">DAY {day_num} &nbsp;·&nbsp; {now_str}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# KPI STRIP
# ══════════════════════════════════════════════════════════════
st.markdown(f"""<div class="kpi-strip">
<div class="kpi-block"><div class="kpi-label">Total Power Demand</div><div class="kpi-value {_kc(S['total_load'],BASE_LOAD_MW*1.05,BASE_LOAD_MW*1.12)}">{S['total_load']:.0f}</div><div class="kpi-unit">MEGAWATTS — CITY + DATA CENTERS</div></div>
<div class="kpi-block"><div class="kpi-label">Safety Buffer</div><div class="kpi-value {_kc(S['reserve'],400,300,inv=True)}">{S['reserve']:.0f}</div><div class="kpi-unit">MW SPARE CAPACITY (MIN 350)</div></div>
<div class="kpi-block"><div class="kpi-label">Busiest Power Line</div><div class="kpi-value {_kc(S['max_line'],75,90)}">{S['max_line']:.1f}</div><div class="kpi-unit">% OF MAX CAPACITY</div></div>
<div class="kpi-block"><div class="kpi-label">Grid Voltage</div><div class="kpi-value kpi-dim">{S['v_min']:.4f}</div><div class="kpi-unit">PU — TARGET 0.95 – 1.05</div></div>
<div class="kpi-block"><div class="kpi-label">Data Center Load</div><div class="kpi-value {'kpi-warn' if S['dc_load']>DC_BASELINE else 'kpi-info'}">{S['dc_load']:.1f}</div><div class="kpi-unit">MW · {S['dc_state']}</div></div>
<div class="kpi-block"><div class="kpi-label">AI Risk Score</div><div class="kpi-value {_kc(S['overall_risk'],.35,.65)}">{S['overall_risk']:.3f}</div><div class="kpi-unit">0 = SAFE &nbsp; 1 = CRITICAL</div></div>
<div class="kpi-block"><div class="kpi-label">Active Events</div><div class="kpi-value {'kpi-warn' if S['active_events'] else 'kpi-ok'}">{len(S['active_events'])}</div><div class="kpi-unit">DATA CENTER DISRUPTIONS</div></div>
<div class="kpi-block"><div class="kpi-label">Violations</div><div class="kpi-value {'kpi-crit' if S['violations'] else 'kpi-ok'}">{len(S['violations'])}</div><div class="kpi-unit">OPERATING LIMITS BREACHED</div></div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ALARM STRIP
# ══════════════════════════════════════════════════════════════
alarm_html = '<div class="alarm-strip"><span style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;white-space:nowrap">LIVE ALARMS &nbsp;|&nbsp;</span>'
if not S["violations"] and not S["active_events"]:
    alarm_html += '<span class="alarm-item alarm-ok">✓ ALL SYSTEMS NORMAL</span>'
else:
    for v in S["violations"]:
        cls = "alarm-crit" if v["sev"]=="CRIT" else "alarm-warn"
        alarm_html += f'<span class="alarm-item {cls}">⚠ {v["name"]} AT {v["val"]}</span>'
    for ev in S["active_events"]:
        alarm_html += f'<span class="alarm-item alarm-warn">⚡ {ev["name"]}</span>'
alarm_html += f'<span class="alarm-ts">{now_str}</span></div>'
st.markdown(alarm_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ACTION PANEL  — shown prominently when decision is needed
# ══════════════════════════════════════════════════════════════
if needs_decision:
    plain_label, plain_explain = ACTION_PLAIN.get(S["b2"], ("Review situation",""))
    conf_col = {"HIGH":"#e74c3c","MEDIUM":"#f0a030"}.get(S["conf"],"#4ac8f0")
    ev_plain = current_event["plain"] if current_event else ""

    st.markdown(f"""
    <div style="background:rgba(231,76,60,.07);border:1px solid rgba(231,76,60,.35);border-left:4px solid #e74c3c;
         padding:14px 20px;margin:8px 0 4px;border-radius:2px">
      <div style="font-family:'Share Tech Mono';font-size:10px;color:#e74c3c;letter-spacing:.15em;margin-bottom:6px">
        ⚠  OPERATOR ACTION REQUESTED
      </div>
      <div style="display:flex;gap:24px;align-items:flex-start">
        <div style="flex:2">
          <div style="font-family:'Rajdhani';font-size:16px;color:#ffa0a0;font-weight:600;margin-bottom:4px">
            {ev_plain if ev_plain else S['why']}
          </div>
          <div style="font-family:'Rajdhani';font-size:13px;color:#c8e0c0;margin-top:6px;line-height:1.5">
            {S['why']}
          </div>
        </div>
        <div style="flex:1;background:rgba(231,76,60,.1);border:1px solid rgba(231,76,60,.3);border-radius:2px;padding:10px;text-align:center">
          <div style="font-family:'Share Tech Mono';font-size:9px;color:#e74c3c;letter-spacing:.12em;margin-bottom:6px">AI RECOMMENDS</div>
          <div style="font-family:'Share Tech Mono';font-size:15px;color:#ff8080;margin-bottom:4px">{S['b2']}</div>
          <div style="font-family:'Rajdhani';font-size:13px;color:#ffa080;font-weight:600">{plain_label}</div>
          <div style="font-family:'Share Tech Mono';font-size:9px;color:{conf_col};margin-top:6px">CONFIDENCE: {S['conf']}</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Highlighted action buttons
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    bc1, bc2, bc3, bc4, bc5 = st.columns([1.8, 1.2, 1.2, 1.2, 1.2])

    with bc1:
        # The recommended action — highlighted and pulsing
        st.markdown('<div class="btn-highlight">', unsafe_allow_html=True)
        if st.button(f"⚡ {plain_label.upper()}  ← DO THIS NOW", key="btn_recommend"):
            st.session_state.action_taken[S["tick"]] = S["b2"]
            # Apply action to grid
            if S["b2"] == "CURTAIL_LOAD":
                st.session_state.manual_mw -= 22.0
            elif S["b2"] == "DEFER_WORKLOAD":
                st.session_state.manual_mw -= 16.0
            st.session_state.runtime_log.insert(0, dict(tick=S["tick"], time=S["time"],
                ev=dict(name=f"OPERATOR ACTION: {S['b2']}", etype="OPERATOR"), status="APPLIED"))
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with bc2:
        st.markdown('<div class="btn-recommend">', unsafe_allow_html=True)
        if st.button("DEFER WORKLOAD", key="btn_defer"):
            st.session_state.manual_mw -= 16.0
            st.session_state.runtime_log.insert(0, dict(tick=S["tick"], time=S["time"],
                ev=dict(name="OPERATOR: DEFER_WORKLOAD", etype="OPERATOR"), status="APPLIED"))
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with bc3:
        if st.button("CURTAIL LOAD", key="btn_curtail"):
            st.session_state.manual_mw -= 22.0
            st.session_state.runtime_log.insert(0, dict(tick=S["tick"], time=S["time"],
                ev=dict(name="OPERATOR: CURTAIL_LOAD", etype="OPERATOR"), status="APPLIED"))
            st.rerun()

    with bc4:
        if st.button("RESTORE NORMAL", key="btn_restore"):
            st.session_state.manual_mw = 0.0
            st.session_state.runtime_log.insert(0, dict(tick=S["tick"], time=S["time"],
                ev=dict(name="OPERATOR: RESTORE", etype="OPERATOR"), status="APPLIED"))
            st.rerun()

    with bc5:
        if st.button("↺  RESET SIM", key="btn_reset_action"):
            reset(); st.rerun()

else:
    # Normal controls when no action needed
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    nc1, nc2, nc3, nc4 = st.columns([1,1,1,3])
    with nc1:
        if st.button("⏸ PAUSE" if st.session_state.running else "▶ RUN"):
            st.session_state.running = not st.session_state.running; st.rerun()
    with nc2:
        if st.button("↺ RESET"):
            reset(); st.rerun()
    with nc3:
        speed = st.select_slider("SPEED", options=["0.5 s","1 s","2 s","5 s"], value="1 s", label_visibility="visible")
        st.session_state.speed = speed
    with nc4:
        next_ev = next((e for e in DEMO_EVENTS if e["tick"] > S["tick"]), None)
        if next_ev:
            ticks_away = next_ev["tick"] - S["tick"]
            mins_away  = ticks_away * 10
            st.markdown(f'<div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;padding-top:10px;letter-spacing:.1em">NEXT EVENT: <span style="color:#f0a030">{next_ev["name"]}</span> in {ticks_away} ticks ({mins_away} min sim time)</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
tab_live, tab_lines, tab_brain, tab_events = st.tabs([
    "  LIVE MONITOR  ", "  POWER LINES  ", "  AI AGENT  ", "  EVENT LOG  "
])

# ── TAB 1: LIVE MONITOR ──────────────────────────────────────
with tab_live:
    col_charts, col_right = st.columns([3, 1.1])

    with col_charts:
        if not hist_df.empty:
            st.markdown('<div class="scada-card-title" style="padding:8px 0 4px;font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.18em">TOTAL POWER DEMAND (MW) — LIVE TREND</div>', unsafe_allow_html=True)
            st.line_chart(hist_df.set_index("time")[["load","dc"]].rename(columns={"load":"City + Data Centers (MW)","dc":"Data Center Only (MW)"}), color=["#2ecc71","#f0a030"], height=155)

            st.markdown('<div class="scada-card-title" style="padding:8px 0 4px;font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.18em">SAFETY BUFFER (MW) · BUSIEST LINE LOADING (%)</div>', unsafe_allow_html=True)
            st.line_chart(hist_df.set_index("time")[["reserve","line"]].rename(columns={"reserve":"Safety Buffer (MW)","line":"Busiest Line (%)"}), color=["#4ac8f0","#e74c3c"], height=135)

            st.markdown('<div class="scada-card-title" style="padding:8px 0 4px;font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.18em">AI RISK SCORE (0 = SAFE · 1 = CRITICAL)</div>', unsafe_allow_html=True)
            st.line_chart(hist_df.set_index("time")[["risk"]].rename(columns={"risk":"Risk Score"}), color=["#e74c3c"], height=110)
        else:
            st.markdown('<div style="font-family:Share Tech Mono;font-size:11px;color:#2a5a2a;padding:60px 0;text-align:center">SIMULATION STARTING — FIRST EVENT AT TICK 36 (06:00)</div>', unsafe_allow_html=True)

    with col_right:
        rc = _rc(S["overall_risk"]); pct = S["overall_risk"]*100
        rlabel = "CRITICAL" if S["overall_risk"]>=0.65 else "ELEVATED" if S["overall_risk"]>=0.35 else "SAFE"
        plain_risk = ("The grid is under significant stress. See the action buttons above." if S["overall_risk"]>=0.65
                      else "Some conditions are elevated. The agent is watching closely." if S["overall_risk"]>=0.35
                      else "The grid is operating normally. No action needed.")
        st.markdown(f'<div class="scada-card" style="text-align:center;padding:16px 12px"><div class="scada-card-title" style="text-align:center">GRID HEALTH</div><div class="risk-big" style="color:{rc}">{S["overall_risk"]:.3f}</div><div style="font-family:Share Tech Mono;font-size:11px;letter-spacing:.2em;color:{rc};margin-top:4px">{rlabel}</div><div class="risk-bar-wrap" style="margin:10px 0 4px"><div class="risk-bar" style="width:{pct:.1f}%;background:{rc}"></div></div><div style="font-family:Rajdhani;font-size:12px;color:#7ab08a;margin-top:8px;line-height:1.4;text-align:left">{plain_risk}</div></div>', unsafe_allow_html=True)

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        dc_pct = (S["dc_load"]-80)/60*100
        dc_col = "#e74c3c" if S["dc_load"]>130 else "#f0a030" if S["dc_load"]>DC_BASELINE else "#4ac8f0"
        plain_dc = DC_STATE_PLAIN.get(S["dc_state"],"")
        st.markdown(f'<div class="scada-card" style="padding:12px"><div class="scada-card-title">DATA CENTER STATUS</div><div style="font-family:Share Tech Mono;font-size:24px;color:{dc_col};line-height:1">{S["dc_load"]:.1f} <span style="font-size:10px;color:#2a5a2a">MW</span></div><div style="font-family:Share Tech Mono;font-size:10px;color:{dc_col};margin-top:3px">{S["dc_state"]}</div><div class="risk-bar-wrap" style="margin:8px 0 4px"><div class="risk-bar" style="width:{dc_pct:.1f}%;background:{dc_col}"></div></div><div style="display:flex;justify-content:space-between;font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;margin-bottom:8px"><span>80</span><span>110 normal</span><span>140 MW</span></div><div style="font-family:Rajdhani;font-size:12px;color:#7ab08a;line-height:1.4">{plain_dc}</div></div>', unsafe_allow_html=True)

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        viol_inner = '<div style="font-family:Share Tech Mono;font-size:10px;color:#2ecc71;padding:8px 0;text-align:center">✓ NO VIOLATIONS</div>'
        if S["violations"]:
            viol_inner = ""
            pv_map = {"Nevada→Benning":"This power line is carrying more than designed — risk of automatic trip.",
                      "Reserve Margin":"Safety buffer is dangerously thin.",
                      "Bus Voltage":"Voltage is outside the normal safe band."}
            for v in S["violations"]:
                cls = "st-crit" if v["sev"]=="CRIT" else "st-warn"
                pv = next((t for k,t in pv_map.items() if k in v["name"]),"Operating limit breached.")
                viol_inner += f'<div style="padding:6px 0;border-bottom:1px solid #0a1a0a"><div style="display:flex;justify-content:space-between;align-items:center"><div class="oneline-name">{v["name"]}</div><div style="display:flex;gap:6px;align-items:center"><div class="oneline-val">{v["val"]}</div><div class="oneline-status {cls}">{v["sev"]}</div></div></div><div style="font-family:Rajdhani;font-size:11px;color:#6a9a6a;margin-top:3px">{pv}</div></div>'
        st.markdown(f'<div class="scada-card"><div class="scada-card-title">LIMIT VIOLATIONS</div>{viol_inner}</div>', unsafe_allow_html=True)

# ── TAB 2: POWER LINES ───────────────────────────────────────
with tab_lines:
    pl1, pl2 = st.columns(2)
    with pl1:
        tx_html = ""
        for i,(name,pct) in enumerate(zip(TX_LINES, S["line_pcts"])):
            cls = "st-crit" if pct>=90 else "st-warn" if pct>=75 else "st-ok"
            bar_c = "#e74c3c" if pct>=90 else "#f0a030" if pct>=75 else "#2ecc71"
            lbl = "OVERLOADED" if pct>=100 else "HIGH" if pct>=75 else "OK"
            tx_html += f'<div style="padding:5px 0;border-bottom:1px solid #0a1a0a"><div style="display:flex;justify-content:space-between;align-items:center"><div class="oneline-name">{name}</div><div style="display:flex;gap:6px;align-items:center"><div style="font-family:Share Tech Mono;font-size:11px;color:{bar_c}">{pct:.1f}%</div><div class="oneline-status {cls}" style="font-size:8px">{lbl}</div></div></div><div style="height:3px;background:#0d1f0d;border-radius:2px;margin-top:3px;overflow:hidden"><div style="height:100%;width:{min(100,pct):.1f}%;background:{bar_c};border-radius:2px"></div></div></div>'
        st.markdown(f'<div class="scada-card"><div class="scada-card-title">Transmission Lines — Live Loading</div>{tx_html}<div class="plain-box" style="margin-top:10px"><div class="plain-title">Plain English</div><div class="plain-text">These are the main power highways across DC. Each bar shows how full that highway is. Above 90% is dangerous — like a freeway at a complete standstill. The busiest right now is at <b>{S["max_line"]:.0f}%</b>.</div></div></div>', unsafe_allow_html=True)

    with pl2:
        gen_html = ""
        for name,p,pmax,desc in [("Benning Road (Main)",850,1500,"Primary generator — slack bus"),("Georgetown",200,300,"Backup — west DC"),("Buzzard Point",150,250,"Backup — southwest DC")]:
            gen_html += f'<div style="padding:7px 0;border-bottom:1px solid #0a1a0a"><div style="display:flex;justify-content:space-between"><div><div class="oneline-name">{name}</div><div style="font-family:Rajdhani;font-size:11px;color:#4a8a4a">{desc}</div></div><div style="text-align:right"><div style="font-family:Share Tech Mono;font-size:12px;color:#c8f0c0">{p} MW</div><div class="oneline-status st-ok">ONLINE</div></div></div><div class="risk-bar-wrap" style="margin:4px 0 0"><div class="risk-bar" style="width:{p/pmax*100:.0f}%;background:#2ecc71"></div></div></div>'
        st.markdown(f'<div class="scada-card"><div class="scada-card-title">Power Stations</div>{gen_html}<div style="font-family:Share Tech Mono;font-size:10px;color:#2a5a2a;padding-top:8px;border-top:1px solid #0a1a0a;display:flex;justify-content:space-between"><span>Total capacity</span><span style="color:#4ac8f0">2,050 MW</span></div></div>', unsafe_allow_html=True)

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        der_html = ""
        for name,mw,loc in [("Mt Vernon Square",15,"NE"),("Navy Yard",20,"SE"),("Shaw",10,"NW"),("NoMa",12,"NE"),("Capitol Hill",8,"SE"),("Howard Univ",5,"NW")]:
            der_html += f'<div class="oneline-row"><div><div class="oneline-name">{name}</div><div style="font-family:Rajdhani;font-size:11px;color:#3a6a3a">{loc} DC</div></div><div style="display:flex;gap:6px;align-items:center"><div class="oneline-val">{mw} MW</div><div class="oneline-status st-ok">ON</div></div></div>'
        st.markdown(f'<div class="scada-card"><div class="scada-card-title">Local Renewables (Solar/DER)</div>{der_html}<div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;padding-top:6px;border-top:1px solid #0a1a0a">70 MW total — reduces load on main generators</div></div>', unsafe_allow_html=True)

# ── TAB 3: AI AGENT ──────────────────────────────────────────
with tab_brain:
    ab1, ab2 = st.columns([1, 1.4])
    with ab1:
        def sbar(val, label, plain):
            col = _rc(val)
            return f'<div style="padding:8px 0;border-bottom:1px solid #0a1a0a"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px"><div><div style="font-family:Share Tech Mono;font-size:10px;color:#4a8a4a">{label}</div><div style="font-family:Rajdhani;font-size:11px;color:#5a9a5a">{plain}</div></div><div style="font-family:Share Tech Mono;font-size:16px;color:{col};min-width:38px;text-align:right">{val:.2f}</div></div><div class="risk-bar-wrap" style="margin:0"><div class="risk-bar" style="width:{val*100:.1f}%;background:{col}"></div></div></div>'
        threat_plain = {"line":"A transmission line is the biggest concern.","reserve":"Low spare capacity is the main risk.","voltage":"Voltage is outside the normal band.","none":"No dominant threat — grid is stable."}.get(S["top_threat"],"")
        st.markdown(f'<div class="scada-card"><div class="scada-card-title">Brain 1 — Automated Risk Scoring</div><div style="font-family:Rajdhani;font-size:12px;color:#5a9a6a;margin-bottom:10px;line-height:1.4">Scores three grid conditions every 10 minutes on a 0–1 scale. Above 0.65 triggers Brain 2 to recommend action.</div>{sbar(S["b1_line"],"TRANSMISSION LINE RISK","How close are lines to their limit?")}{sbar(S["b1_res"],"RESERVE CAPACITY RISK","How thin is our safety buffer?")}{sbar(S["b1_volt"],"VOLTAGE STABILITY RISK","Is voltage in the safe band?")}<div style="margin-top:10px;padding-top:8px;border-top:1px solid #0a1a0a"><div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.1em">BIGGEST CONCERN</div><div style="font-family:Share Tech Mono;font-size:14px;color:{_rc(S["overall_risk"])};margin-top:2px">{S["top_threat"].upper()}</div><div style="font-family:Rajdhani;font-size:12px;color:#5a9a6a;margin-top:3px">{threat_plain}</div></div></div>', unsafe_allow_html=True)

    with ab2:
        ac = _ac(S["b2"])
        conf_col = {"HIGH":"#e74c3c","MEDIUM":"#f0a030"}.get(S["conf"],"#4ac8f0")
        plain_label, plain_explain = ACTION_PLAIN.get(S["b2"], ("",""))
        conf_plain = {"HIGH":"Very confident — data strongly supports this.","MEDIUM":"Reasonably confident — monitoring.","LOW":"Uncertain — human review recommended."}.get(S["conf"],"")
        st.markdown(f'<div class="scada-card"><div class="scada-card-title">Brain 2 — AI Reasoning Agent (Claude)</div><div style="font-family:Rajdhani;font-size:12px;color:#5a9a6a;margin-bottom:10px;line-height:1.4">Reads Brain 1\'s scores, considers demand trends and market signals, and reasons about what to do next — like a senior operator who never sleeps.</div><div class="b2-box"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div style="font-family:Share Tech Mono;font-size:9px;color:#2a4a6a;letter-spacing:.12em;margin-bottom:4px">RECOMMENDED ACTION</div><div style="font-family:Share Tech Mono;font-size:14px;color:{ac}">{S["b2"]}</div><div style="font-family:Rajdhani;font-size:15px;color:#a8d0f0;margin-top:3px;font-weight:600">→ {plain_label}</div><div style="font-family:Share Tech Mono;font-size:10px;color:#2a6a8a;margin-top:2px">TARGET: {S["target"]}</div></div><div style="text-align:right"><div style="font-family:Share Tech Mono;font-size:9px;color:#2a4a6a;letter-spacing:.1em">CONFIDENCE</div><div style="font-family:Share Tech Mono;font-size:18px;color:{conf_col}">{S["conf"]}</div><div style="font-family:Rajdhani;font-size:10px;color:#5a8a9a;max-width:120px;text-align:right;margin-top:2px">{conf_plain}</div></div></div></div><div style="font-family:Share Tech Mono;font-size:9px;color:#2a4a6a;letter-spacing:.1em;margin-top:10px;margin-bottom:4px">WHAT THIS MEANS</div><div style="font-family:Rajdhani;font-size:13px;color:#7ab0c8;line-height:1.6;padding:10px;background:rgba(42,122,170,.05);border:1px solid #0a2030;border-radius:2px">{plain_explain}</div><div style="font-family:Share Tech Mono;font-size:9px;color:#2a4a6a;letter-spacing:.1em;margin-top:10px;margin-bottom:4px">TECHNICAL REASONING</div><div style="font-family:Rajdhani;font-size:12px;color:#5a8a9a;line-height:1.5;padding:8px;background:rgba(0,0,0,.2);border-radius:2px">{S["why"]}</div></div>', unsafe_allow_html=True)

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.18em;padding:4px 0">RECENT AGENT DECISIONS</div>', unsafe_allow_html=True)
    log_inner = ""
    if not st.session_state.agent_log:
        log_inner = '<div style="font-family:Share Tech Mono;font-size:10px;color:#2a5a2a;padding:16px 0;text-align:center">NO INTERVENTIONS YET — FIRST EVENT FIRES AT TICK 36 (06:00)</div>'
    for entry in st.session_state.agent_log[:20]:
        ac2 = _ac(entry["action"]); pl2 = ACTION_PLAIN.get(entry["action"],("",""))[0]
        log_inner += f'<div class="evlog-row"><div class="evlog-tick">{entry["time"]}<br>T:{entry["tick"]:04d}</div><div class="evlog-dot" style="background:{ac2}"></div><div><div class="evlog-msg"><span style="color:{ac2}">{entry["action"]}</span> → {entry["target"]} · risk {entry["risk"]:.3f}</div><div style="font-family:Rajdhani;font-size:11px;color:#4a7a5a">{pl2}</div></div></div>'
    st.markdown(f'<div class="scada-card"><div class="log-scroll">{log_inner}</div></div>', unsafe_allow_html=True)

# ── TAB 4: EVENT LOG ─────────────────────────────────────────
with tab_events:
    el1, el2 = st.columns(2)
    type_colors = {"AI_TRAINING_SPIKE":"#f0a030","AI_TRAINING_DROPOUT":"#e74c3c","COOLING_CASCADE":"#f0a030","LOAD_OSCILLATION":"#4ac8f0","OPERATOR":"#2ecc71","MANUAL":"#e74c3c"}

    with el1:
        st.markdown('<div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.18em;padding:4px 0">SCHEDULED EVENTS (from run_live.py)</div>', unsafe_allow_html=True)
        sched_html = ""
        for ev in DEMO_EVENTS:
            is_active = ev["tick"] <= S["tick"] < ev["tick"]+ev["dur"]
            is_past   = S["tick"] >= ev["tick"]+ev["dur"]
            st_cls = "st-ok" if is_active else "st-crit" if not is_past else "st-warn"
            st_lbl = "● ACTIVE NOW" if is_active else f"○ STARTS AT {tick_to_time(ev['tick'])}" if not is_past else "✓ COMPLETED"
            ec = type_colors.get(ev["etype"],"#a8c8a0")
            progress = min(100,max(0,(S["tick"]-ev["tick"])/ev["dur"]*100)) if is_active else (100 if is_past else 0)
            sched_html += f'<div style="padding:10px 0;border-bottom:1px solid #0a1a0a"><div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px"><div><div style="font-family:Share Tech Mono;font-size:9px;color:{ec};letter-spacing:.1em">{ev["etype"].replace("_"," ")}</div><div style="font-family:Rajdhani;font-size:14px;color:#a8c8a0;font-weight:600;margin-top:2px">{ev["name"]}</div><div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;margin-top:2px">Ticks {ev["tick"]}–{ev["tick"]+ev["dur"]} &nbsp;·&nbsp; {ev["dur"]*10} min &nbsp;·&nbsp; DC_NoMa</div></div><div class="oneline-status {st_cls}" style="white-space:nowrap;font-size:9px">{st_lbl}</div></div>{"<div class='risk-bar-wrap'><div class='risk-bar' style='width:"+str(progress)+"%;background:"+ec+"'></div></div>" if is_active or is_past else ""}<div style="font-family:Rajdhani;font-size:12px;color:#5a8a6a;margin-top:5px;line-height:1.4">{ev["plain"]}</div></div>'
        st.markdown(f'<div class="scada-card">{sched_html}</div>', unsafe_allow_html=True)

    with el2:
        st.markdown('<div style="font-family:Share Tech Mono;font-size:9px;color:#2a5a2a;letter-spacing:.18em;padding:4px 0">LIVE ALARM & ACTION LOG</div>', unsafe_allow_html=True)
        rt_inner = ""
        if not st.session_state.runtime_log:
            rt_inner = '<div style="font-family:Share Tech Mono;font-size:10px;color:#2a5a2a;padding:20px 0;text-align:center">RUNNING — FIRST EVENT FIRES AT TICK 36 (06:00 SIM TIME)</div>'
        for entry in st.session_state.runtime_log[:35]:
            status = entry["status"]
            dot_c = "#f0a030" if status=="FIRED" else "#2ecc71" if status in ("CLEARED","APPLIED") else "#4ac8f0"
            ev_name = entry["ev"]["name"] if isinstance(entry["ev"], dict) else str(entry["ev"])
            rt_inner += f'<div class="evlog-row"><div class="evlog-tick">{entry["time"]}<br>T:{entry["tick"]:04d}</div><div class="evlog-dot" style="background:{dot_c}"></div><div><div class="evlog-msg"><span style="color:{dot_c}">[{status}]</span> &nbsp;{ev_name.replace("_"," ")}</div></div></div>'
        st.markdown(f'<div class="scada-card"><div class="log-scroll" style="height:420px">{rt_inner}</div></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# AUTO REFRESH
# ══════════════════════════════════════════════════════════════
if st.session_state.running:
    delay = {"0.5 s":0.5,"1 s":1.0,"2 s":2.0,"5 s":5.0}.get(getattr(st.session_state,"speed","1 s"),1.0)
    time.sleep(delay)
    st.rerun()
