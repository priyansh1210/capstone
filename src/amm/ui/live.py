"""State and queries behind the dashboard (kept out of the Streamlit file).

A LiveDemo owns one Session per policy (the selected policy and, optionally,
a static baseline) replaying the *same* scenario in lock-step. A demo demand
change is applied to every session's simulator (it changes the world), fault
injections only to the selected policy. All numbers shown come from the
engine's SQLite records and in-memory registry; nothing is synthesised for display.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from amm import paths
from amm.config import load_config
from amm.data import scenarios
from amm.engine import Session, train_initial
from amm.storage.store import Store

DB = paths.ARTIFACTS / "dashboard.sqlite"
CKPT = paths.ARTIFACTS / "dashboard"


class LiveDemo:
    def __init__(self, scenario: str, policy: str, seed: int, compare_static: bool = True, config: str = "configs/demo.yaml"):
        self.cfg = load_config(config)
        sc = scenarios.build(scenario, self.cfg, seed if scenario.startswith("synthetic") else None)
        init = train_initial(sc, self.cfg)
        self.store = Store(DB)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.stamp = stamp
        self.primary = policy
        self.sessions: dict[str, Session] = {}
        for p in [policy] + (["static"] if compare_static and policy != "static" else []):
            self.sessions[p] = Session(sc, p, self.cfg, self.store, run_id=f"demo-{stamp}-{p}", initial=init,
                                       artifact_root=paths.ARTIFACTS / "dashboard_runs", notes="dashboard")
        # Evaluator-side information, shown in the UI and never passed to a controller.
        self.meta = {
            "scenario": sc.name, "kind": sc.kind, "kind_label": sc.kind_label, "description": sc.description,
            "manifest": json.loads(json.dumps(sc.manifest, default=str)), "seed": seed,
            "replay_range": [str(sc.replay["ts_local"].min()), str(sc.replay["ts_local"].max())],
            "initial_reference_mae": init[1].reference_mae,
        }
        self.injections: list[dict] = []

    # --------------------------------------------------------------- control
    @property
    def main(self) -> Session:
        return self.sessions[self.primary]

    @property
    def finished(self) -> bool:
        return all(s.finished for s in self.sessions.values())

    def step(self, n: int = 1) -> int:
        done = 0
        for _ in range(n):
            if self.finished:
                break
            for s in self.sessions.values():
                s.step()
            done += 1
        return done

    def fast_forward(self, until: pd.Timestamp) -> int:
        n = 0
        while not self.finished and self.main.sim.batch_start_ts(self.main.t) < until:
            n += self.step(1)
        return n

    def inject_demand_change(self, factor: float, hours: list[int], workingday_only: bool) -> dict:
        label = f"x{factor:g} demand in hours {hours}{' on working days' if workingday_only else ''}"
        rec = None
        for s in self.sessions.values():
            ch = s.inject_demand_change(factor, hours, workingday_only, label)
            rec = {"from_batch": ch.from_batch, "from_date": str(s.sim.batch_start_ts(ch.from_batch).date()), "label": label, "rows": ch.rows_affected}
        self.injections.append(rec)
        return rec

    def save(self) -> Path:
        CKPT.mkdir(parents=True, exist_ok=True)
        for p, s in self.sessions.items():
            s.save(CKPT / f"{s.run_id}.joblib")
        meta = {"stamp": self.stamp, "primary": self.primary, "policies": list(self.sessions), "meta": self.meta,
                "injections": self.injections, "cfg": "configs/demo.yaml"}
        (CKPT / "latest.json").write_text(json.dumps(meta, default=str))
        return CKPT

    @classmethod
    def load_latest(cls) -> "LiveDemo | None":
        f = CKPT / "latest.json"
        if not f.exists():
            return None
        m = json.loads(f.read_text())
        obj = cls.__new__(cls)
        obj.store = Store(DB)
        obj.stamp, obj.primary, obj.meta, obj.injections = m["stamp"], m["primary"], m["meta"], m["injections"]
        obj.sessions = {p: Session.load(CKPT / f"demo-{m['stamp']}-{p}.joblib", obj.store) for p in m["policies"]}
        obj.cfg = obj.main.cfg
        return obj

    # --------------------------------------------------------------- queries
    def kpis(self) -> dict:
        s = self.main
        c = s.controller
        sim = s.sim
        ev = pd.DataFrame(c.events)
        cnt = ev["action"].value_counts() if len(ev) else pd.Series(dtype=int)
        r = c.monitor.rolling()
        return {
            "date": sim.batch_start_ts(min(s.t, sim.n_batches - 1)).date(),
            "step": s.t, "total": sim.total_steps,
            "state": c.state.value, "active": c.registry.active_id, "active_model": c.registry.active.model_name,
            "previous": c.registry.previous_id,
            "cycles": c.cycle, "fits": c.fits, "train_seconds": c.train_seconds,
            "promotions": int(cnt.get("PROMOTED", 0)), "rejections": int(cnt.get("CANDIDATES_REJECTED", 0)),
            "rollbacks": int(cnt.get("ROLLED_BACK", 0)), "alarms": int(cnt.get("ALARM", 0)),
            "rolling_mae": r["mae"], "rolling_rmse": r["rmse"], "rolling_n": r["n"],
            "labelled_since_rebase": c.monitor.n,
        }

    def recent(self, days: int = 14) -> pd.DataFrame:
        s = self.main
        lo = max(0, s.t - days)
        return self.store.query(
            "SELECT ts, batch, model_version, y_pred, y_true, abs_err FROM predictions WHERE run_id=? AND role='active' AND prediction_step>=? ORDER BY seq",
            (s.run_id, lo),
        ).assign(ts=lambda d: pd.to_datetime(d["ts"]))

    def daily(self) -> pd.DataFrame:
        out = []
        for p, s in self.sessions.items():
            d = self.store.query(
                "SELECT batch, MIN(ts) day, AVG(abs_err) mae, SQRT(AVG(abs_err*abs_err)) rmse, COUNT(*) n FROM predictions "
                "WHERE run_id=? AND role='active' AND y_true IS NOT NULL GROUP BY batch ORDER BY batch",
                (s.run_id,),
            )
            d["policy"] = p
            out.append(d)
        d = pd.concat(out, ignore_index=True)
        d["day"] = pd.to_datetime(d["day"]).dt.normalize()
        return d

    def events(self) -> pd.DataFrame:
        ev = pd.DataFrame(self.main.controller.events)
        if ev.empty:
            return ev
        ev["date"] = pd.to_datetime(ev["ts"]).dt.date
        return ev

    def versions(self) -> pd.DataFrame:
        reg = self.main.controller.registry
        rows = []
        for v in reg.versions.values():
            rows.append({
                "version": v.version, "status": v.status, "model": v.model_name, "window_days": v.window_days,
                "train": f"{(v.train_start or '')[:10]} -> {(v.train_end or '')[:10]}", "n_train": v.n_train,
                "validation": f"{(v.val_start or '')[:10]} -> {(v.val_end or '')[:10]}" if v.val_start else "-",
                "val_MAE": v.val_mae, "current_val_MAE": v.current_val_mae, "reference_signal": v.reference_signal,
                "reference_source": v.reference_source, "fit_s": round(v.train_seconds, 2), "cycle": v.cycle,
                "created_step": v.created_step, "activated_step": v.activated_step, "retired_step": v.retired_step,
                "test_only_fault": v.fault_injection, "notes": v.notes,
            })
        return pd.DataFrame(rows)
