"""Streamlit dashboard for the autonomous model-maintenance supervisor.

Run:  .venv\\Scripts\\python -m streamlit run app/dashboard.py

UI only: all state lives in amm.ui.live.LiveDemo (engine Sessions + SQLite).
Buttons act through callbacks, so a Streamlit rerun never repeats an action;
steps are guarded by the engine's lock and duplicate-step check; a run is only
replaced when "Create new run" is pressed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from amm import paths  # noqa: E402
from amm.data.fallback import is_fallback  # noqa: E402
from amm.ui.live import LiveDemo  # noqa: E402

st.set_page_config(page_title="Autonomous Model Maintenance", layout="wide", page_icon=":material/monitoring:")

SCENARIOS = {
    "bike_unmodified": "Source observations: 2018-2024 replay, unmodified",
    "bike_abrupt": "Modified observations: injected abrupt change (Apr 2019)",
    "bike_gradual": "Modified observations: injected gradual change (Mar-Sep 2019)",
    "synthetic_stationary": "Generated: stationary synthetic stream",
    "synthetic_abrupt": "Generated: synthetic stream with abrupt change",
}
POLICIES = ["probe", "adaptive", "periodic", "static"]
ACTION_GROUPS = {
    "Detection": ["ALARM", "ALARM_DISMISSED", "CHANGE_IGNORED", "DETERIORATION_CONFIRMED", "DETERIORATION_PERSISTS", "DETERIORATION_RESOLVED"],
    "Waiting": ["WAIT", "RETRAIN_POSTPONED", "RETRAIN_DECLINED", "RETRAIN_REQUESTED", "OPERATOR_REQUEST"],
    "Retraining": ["PROBE", "RETRAIN_START", "CANDIDATES_REJECTED", "PROMOTED", "TRAINING_FAILED", "PROMOTION_FAILED"],
    "Probation": ["PROBATION_CHECK", "KEPT", "ROLLED_BACK"],
    "Test-only": ["FAULT_INJECTION", "FAULT_INJECTION_ACTIVATION", "FAULT_INJECTION_REFUSED"],
}


# ------------------------------------------------------------------ theme
def theme():
    try:
        dark = st.context.theme.type == "dark"
    except Exception:
        dark = False
    if dark:
        return {"dark": True, "text": "#f0efec", "text2": "#c3c2b7", "grid": "#2c2c2a", "axis": "#383835",
                "pol": {"probe": "#3987e5", "adaptive": "#c3c2b7", "periodic": "#d95926", "static": "#199e70"}, "actual": "#f0efec"}
    return {"dark": False, "text": "#0b0b0b", "text2": "#52514e", "grid": "#e1e0d9", "axis": "#c3c2b7",
            "pol": {"probe": "#2a78d6", "adaptive": "#52514e", "periodic": "#eb6834", "static": "#1baf7a"}, "actual": "#0b0b0b"}


def style(fig, T, height=330, ytitle=""):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=36, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=T["text2"], size=12), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=T["text"])),
    )
    fig.update_xaxes(showgrid=False, linecolor=T["axis"], tickcolor=T["axis"])
    fig.update_yaxes(gridcolor=T["grid"], gridwidth=1, zeroline=False, title_text=ytitle, linecolor=T["axis"])
    return fig


# ------------------------------------------------------------------ state
ss = st.session_state
ss.setdefault("demo", None)
ss.setdefault("running", False)
ss.setdefault("flash", None)


def create_run():
    ss.running = False
    with st.spinner("Building scenario and training the initial model..."):
        ss.demo = LiveDemo(ss.sel_scenario, ss.sel_policy, int(ss.sel_seed), ss.sel_compare)
    ss.flash = f"New run created ({ss.demo.stamp}). Previous runs stay in the database."


def resume_run():
    ss.running = False
    d = LiveDemo.load_latest()
    if d is None:
        ss.flash = "No saved checkpoint found."
    else:
        ss.demo = d
        ss.flash = f"Resumed checkpoint {d.stamp} at step {d.main.t} (database rewound to the checkpoint if it was ahead)."


def do(fn, msg):
    def cb():
        if ss.demo is None:
            return
        out = fn(ss.demo)
        ss.flash = msg(out) if callable(msg) else msg
    return cb


def set_running(v):
    ss.running = v
    if not v and ss.demo is not None:
        ss.demo.save()


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Run setup")
    st.selectbox("Scenario", list(SCENARIOS), format_func=lambda k: SCENARIOS[k], key="sel_scenario")
    st.radio("Policy", POLICIES, horizontal=True, key="sel_policy")
    st.number_input("Seed (generated scenarios)", 1, 999, 1, key="sel_seed")
    st.checkbox("Also run static baseline in lock-step", True, key="sel_compare")
    c1, c2 = st.columns(2)
    c1.button("Create new run", on_click=create_run, type="primary", width="stretch")
    c2.button("Resume saved", on_click=resume_run, width="stretch")
    d = ss.demo
    if d is not None and (d.meta["scenario"] != ss.sel_scenario or d.primary != ss.sel_policy):
        st.caption("Settings differ from the current run. Press **Create new run** to apply them.")

    st.header("Replay")
    st.slider("Speed (days per tick)", 1, 30, 3, key="speed")
    b1, b2, b3 = st.columns(3)
    b1.button("Start", on_click=set_running, args=(True,), disabled=d is None or ss.running, width="stretch")
    b2.button("Pause", on_click=set_running, args=(False,), disabled=d is None or not ss.running, width="stretch")
    b3.button("Step", on_click=do(lambda x: x.step(1), "Advanced one day."), disabled=d is None or ss.running, width="stretch")
    st.date_input("Fast-forward to", value=pd.Timestamp("2019-03-01"), key="ff_date")
    st.button("Fast-forward (runs every step for real)", disabled=d is None or ss.running, width="stretch",
              on_click=do(lambda x: x.fast_forward(pd.Timestamp(ss.ff_date)), lambda n: f"Fast-forwarded {n} days."))

    st.header("Experiment controls")
    st.caption("Changes the simulated world for every policy. The controller is not told.")
    st.slider("Demand factor", 0.3, 2.5, 1.6, 0.1, key="inj_factor")
    st.multiselect("Hours", list(range(24)), [7, 8, 9, 16, 17, 18, 19], key="inj_hours")
    st.checkbox("Working days only", True, key="inj_wd")
    st.button("Inject labelled demand change", disabled=d is None, width="stretch",
              on_click=do(lambda x: x.inject_demand_change(ss.inj_factor, ss.inj_hours, ss.inj_wd),
                          lambda r: f"Injected from {r['from_date']}: {r['label']} ({r['rows']} future rows)."))
    st.button("Operator: request retraining attempt", disabled=d is None, width="stretch",
              on_click=do(lambda x: x.main.operator_request(), lambda ok: "Operator request logged." if ok else "Request refused (see timeline)."))
    st.markdown("**:orange[TEST-ONLY fault injection]**")
    st.caption("Disclosed in the timeline and model registry. Validation, monitoring and rollback logic still run for real.")
    st.button("Next cycle trains only a weak candidate", disabled=d is None, width="stretch",
              on_click=do(lambda x: x.main.inject_weak_candidates(), "TEST-ONLY: weak candidate pool armed for the next cycle."))
    st.button("Force-activate weak model (bypass gate)", disabled=d is None, width="stretch",
              on_click=do(lambda x: x.main.force_activate_weak(), lambda ok: "TEST-ONLY weak model activated; probation running." if ok else "Refused: only possible while serving."))
    st.button("Save checkpoint", disabled=d is None, on_click=do(lambda x: x.save(), "Checkpoint saved."), width="stretch")


# ------------------------------------------------------------------ header
st.title("Autonomous Model Maintenance under Concept Drift")
st.caption("Hourly bike-demand model supervised by an evidence-based retraining controller (Capital Bikeshare + NOAA DCA weather).")
if is_fallback():
    st.error("GENERATED FALLBACK DATA is loaded because the raw sources were unavailable. These are NOT Capital Bikeshare observations.")
if ss.flash:
    st.toast(ss.flash)
    ss.flash = None

if ss.demo is None:
    st.info("No run yet. Choose a scenario and policy in the sidebar, then press **Create new run**. "
            "Use **Resume saved** to reload the last checkpoint.")
    with st.expander("Classroom demo script", expanded=True):
        st.markdown(Path(ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8") if (ROOT / "docs" / "DEMO_SCRIPT.md").exists() else "See docs/DEMO_SCRIPT.md")


def kind_banner(meta):
    k = meta["kind"]
    txt = f"**Data:** {meta['kind_label']}. {meta['description']}"
    (st.success if k == "source" else st.warning if k == "modified" else st.info)(txt)


def overview(demo, T):
    k = demo.kpis()
    kind_banner(demo.meta)
    c = st.columns(6)
    c[0].metric("Replay date", str(k["date"]), f"step {k['step']}/{k['total']}", delta_color="off")
    c[1].metric("Controller state", k["state"])
    c[2].metric("Active model", f"{k['active']} ({k['active_model']})", f"fallback {k['previous']}" if k["previous"] else None, delta_color="off")
    c[3].metric("Rolling MAE, 7 d", f"{k['rolling_mae']:.1f}" if k["rolling_mae"] is not None else "no labels yet",
                f"{k['rolling_n']} labelled h since rebase" if k["rolling_n"] else None, delta_color="off")
    c[4].metric("Retraining cycles", k["cycles"], f"{k['fits']} fits, {k['train_seconds']:.1f} s measured", delta_color="off")
    c[5].metric("Promoted / rejected / rolled back", f"{k['promotions']} / {k['rejections']} / {k['rollbacks']}")
    st.progress(min(1.0, k["step"] / max(1, k["total"])))

    left, right = st.columns(2)
    with left:
        r = demo.recent(14)
        st.markdown("**Actual vs originally predicted demand** (last 14 days, hourly)")
        if r.empty:
            st.caption("No predictions yet. Press Step or Start.")
        else:
            f = go.Figure()
            lab = r.dropna(subset=["y_true"])
            f.add_scatter(x=lab["ts"], y=lab["y_true"], name="actual", line=dict(color=T["actual"], width=2))
            f.add_scatter(x=r["ts"], y=r["y_pred"], name=f"predicted ({demo.primary}, model at prediction time)",
                          line=dict(color=T["pol"][demo.primary], width=2), customdata=r["model_version"],
                          hovertemplate="%{y:.0f} (%{customdata})")
            pend = r[r["y_true"].isna()]
            if len(pend):
                f.add_vrect(x0=pend["ts"].min(), x1=pend["ts"].max(), fillcolor=T["grid"], opacity=0.5, line_width=0,
                            annotation_text="label not yet revealed", annotation_position="top left")
            st.plotly_chart(style(f, T, ytitle="trips / hour"), width="stretch", config={"displayModeBar": False})
    with right:
        dd = demo.daily()
        st.markdown("**Rolling prediction error** (daily MAE, 7-day mean; markers = decisions)")
        if dd.empty:
            st.caption("Error appears once the first labels are revealed (one day after prediction).")
        else:
            f = go.Figure()
            for p, g in dd.groupby("policy"):
                f.add_scatter(x=g["day"], y=g["mae"].rolling(7, min_periods=3).mean(), name=p, line=dict(color=T["pol"][p], width=2))
            ev = demo.events()
            marks = {"PROMOTED": "triangle-up", "ROLLED_BACK": "triangle-down", "CANDIDATES_REJECTED": "x", "DETERIORATION_CONFIRMED": "circle"}
            if not ev.empty:
                y0 = float(dd["mae"].rolling(7, min_periods=1).mean().max())
                for a, sym in marks.items():
                    e = ev[ev["action"] == a]
                    if len(e):
                        f.add_scatter(x=pd.to_datetime(e["ts"]), y=[y0 * 1.05] * len(e), mode="markers", name=a.lower().replace("_", " "),
                                      marker=dict(symbol=sym, size=10, color=T["text2"], line=dict(width=2, color="rgba(0,0,0,0)")),
                                      text=e["reason"], hovertemplate="%{text}")
            for inj in demo.injections:
                f.add_vline(x=pd.Timestamp(inj["from_date"]), line_color=T["text2"], line_width=1)
                f.add_annotation(x=pd.Timestamp(inj["from_date"]), y=1, yref="paper", text="injected change", showarrow=False, font=dict(color=T["text2"], size=11))
            ch = (demo.meta.get("manifest") or {}).get("change")
            if ch:
                f.add_vline(x=pd.Timestamp(ch["start"]), line_color=T["text2"], line_width=1, line_dash="dot")
                f.add_annotation(x=pd.Timestamp(ch["start"]), y=0.92, yref="paper", text="scenario change (hidden from controller)", showarrow=False, font=dict(color=T["text2"], size=11))
            st.plotly_chart(style(f, T, ytitle="MAE (trips / hour)"), width="stretch", config={"displayModeBar": False})
    ev = demo.events()
    if not ev.empty:
        last = ev.iloc[-1]
        st.markdown(f"**Latest decision** ({last['date']}, {last['action']}): {last['reason']}")
    with st.expander("Evaluator view: scenario manifest (never passed to the controller)"):
        st.json(demo.meta["manifest"])
        if demo.injections:
            st.write("Runtime injections:", demo.injections)


def timeline(demo, T):
    ev = demo.events()
    if ev.empty:
        st.info("No decisions recorded yet.")
        return
    groups = st.multiselect("Show", list(ACTION_GROUPS), ["Detection", "Waiting", "Retraining", "Probation", "Test-only"], key="tl_groups")
    keep = {a for g in groups for a in ACTION_GROUPS[g]}
    e = ev[ev["action"].isin(keep)]
    st.caption(f"{len(e)} of {len(ev)} events. Every reason, measurement and threshold below is what the controller logged at that moment.")
    f = go.Figure()
    for i, (g, acts) in enumerate(ACTION_GROUPS.items()):
        x = e[e["action"].isin(acts)]
        if len(x):
            f.add_scatter(x=pd.to_datetime(x["ts"]), y=[g] * len(x), mode="markers", name=g, showlegend=False,
                          marker=dict(size=10, color=T["pol"]["adaptive"] if g != "Test-only" else "#eb6834", line=dict(width=2, color="rgba(0,0,0,0)")),
                          text=x["action"] + ": " + x["reason"], hovertemplate="%{text}<extra></extra>")
    st.plotly_chart(style(f, T, height=230), width="stretch", config={"displayModeBar": False})
    show = e[["event_id", "date", "step", "action", "state_from", "state_to", "reason", "fault_injection"]].iloc[::-1]
    sel = st.dataframe(show, hide_index=True, width="stretch", height=380, on_select="rerun", selection_mode="single-row", key="tl_table")
    rows = sel.selection.rows if sel and sel.selection else []
    if rows:
        evrow = ev[ev["event_id"] == show.iloc[rows[0]]["event_id"]].iloc[0]
        a, b = st.columns(2)
        a.markdown("**Measurements**")
        a.json(evrow["measurements"])
        b.markdown("**Thresholds**")
        b.json(evrow["thresholds"])
    else:
        st.caption("Select a row to see its measurements and thresholds.")


def versions(demo):
    v = demo.versions()
    st.caption("active = serving; previous = fallback kept during probation; retired = replaced after passing probation; "
               "rejected = best candidate of a cycle that failed the validation gate; rolled_back = failed probation; failed = training/saving error.")
    order = {"active": 0, "previous": 1, "candidate": 2, "retired": 3, "rejected": 4, "rolled_back": 5, "failed": 6}
    v = v.assign(_o=v["status"].map(order)).sort_values(["_o", "version"]).drop(columns="_o")
    st.dataframe(v, hide_index=True, width="stretch", height=420,
                 column_config={"val_MAE": st.column_config.NumberColumn(format="%.1f"), "current_val_MAE": st.column_config.NumberColumn(format="%.1f"),
                                "reference_signal": st.column_config.NumberColumn(format="%.3f")})
    cyc = demo.store.query("SELECT cycle, step, trigger, outcome, n_fits, ROUND(seconds,2) seconds, val_start, val_end, n_val, "
                           "ROUND(current_val_mae,1) current_val_mae, ROUND(best_val_mae,1) best_val_mae FROM cycles WHERE run_id=? ORDER BY cycle", (demo.main.run_id,))
    st.markdown("**Retraining cycles** (measured wall time of candidate fits)")
    if cyc.empty:
        st.caption("No retraining cycle yet.")
    else:
        st.dataframe(cyc, hide_index=True, width="stretch")


def experiments(T):
    dirs = [p for p in sorted(paths.REPORTS.iterdir()) if (p / "results.json").exists()] if paths.REPORTS.exists() else []
    if not dirs:
        st.info("No experiment results yet. Run `python -m amm smoke` or `python -m amm benchmark`.")
        return
    pick = st.selectbox("Results", [d.name for d in dirs], index=[d.name for d in dirs].index("benchmark") if any(d.name == "benchmark" for d in dirs) else 0)
    out = paths.REPORTS / pick
    if (out / "cities.csv").exists():  # multi-city evaluation: tables + figures as generated
        st.markdown((out / "summary.md").read_text(encoding="utf-8"))
        for png in sorted(out.glob("fig_*.png")):
            with st.expander(png.name, expanded=png.name.startswith("fig_pareto")):
                st.image(str(png))
        for f in ("results.csv", "summary.csv", "significance.csv", "cities.csv", "ablations.csv"):
            if (out / f).exists():
                st.download_button(f, (out / f).read_bytes(), f, key=f"dl-{pick}-{f}")
        return
    summ = pd.read_csv(out / "summary.csv")
    res = pd.read_csv(out / "results.csv")
    env = json.loads((out / "environment.json").read_text()) if (out / "environment.json").exists() else {}
    st.caption(f"Executed runs: {len(res)}; benchmark wall time {env.get('benchmark_seconds', '?')} s on {env.get('processor', '?')}. "
               "The periodic baseline uses the same validation gate, probation and budget as adaptive; only the trigger differs.")
    groups = {"Source observations (unmodified replay)": ["bike_unmodified"], "Modified observations (injected change)": ["bike_abrupt", "bike_gradual"],
              "Generated data": ["synthetic_stationary", "synthetic_abrupt"]}
    cols = ["scenario", "policy", "runs", "mae", "mae_sd", "rmse", "cycles", "fits", "train_seconds", "promotions", "rejections", "rollbacks",
            "alarms", "detect_delay_days", "mae_post_change_120d", "recovery_days"]
    for title, scs in groups.items():
        t = summ[summ["scenario"].isin(scs)]
        if len(t):
            st.markdown(f"**{title}**")
            st.dataframe(t[[c for c in cols if c in t]].round(2), hide_index=True, width="stretch")
    sc = st.selectbox("Rolling error for scenario", sorted(res["scenario"].unique()))
    sub = res[res["scenario"] == sc]
    if sub["seed"].notna().any():
        sub = sub[sub["seed"] == sub["seed"].min()]
    f = go.Figure()
    for _, r in sub.iterrows():
        fp = out / "daily" / f"{r['run_id']}.csv"
        if fp.exists():
            d = pd.read_csv(fp, parse_dates=["day"])
            f.add_scatter(x=d["day"], y=d["mae"].rolling(28, min_periods=7).mean(), name=r["policy"], line=dict(color=T["pol"].get(r["policy"], T["text2"]), width=2))
    if "change_start" in sub and sub["change_start"].notna().any():
        f.add_vline(x=pd.Timestamp(sub["change_start"].dropna().iloc[0]), line_color=T["text2"], line_width=1)
    st.plotly_chart(style(f, T, ytitle="MAE (28-day rolling)"), width="stretch", config={"displayModeBar": False})
    d1, d2, d3 = st.columns(3)
    d1.download_button("results.csv", (out / "results.csv").read_bytes(), "results.csv", width="stretch")
    d2.download_button("summary.csv", (out / "summary.csv").read_bytes(), "summary.csv", width="stretch")
    d3.download_button("results.json", (out / "results.json").read_bytes(), "results.json", width="stretch")
    for png in sorted(out.glob("fig_*.png")):
        with st.expander(png.name):
            st.image(str(png))


def main_area():
    T = theme()
    demo = ss.demo
    if demo is not None and ss.running:
        if demo.finished:
            ss.running = False
            demo.save()
        else:
            demo.step(int(ss.speed))
    tabs = st.tabs(["Overview", "Decision timeline", "Model versions", "Experiments"])
    with tabs[0]:
        if demo is not None:
            overview(demo, T)
    with tabs[1]:
        if demo is not None:
            timeline(demo, T)
        else:
            st.info("Create a run to see decisions.")
    with tabs[2]:
        if demo is not None:
            versions(demo)
        else:
            st.info("Create a run to see model versions.")
    with tabs[3]:
        experiments(T)


st.fragment(main_area, run_every=1.0 if ss.running else None)()
