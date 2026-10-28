"""Run policies on scenarios and compute comparable metrics from stored predictions.

Fairness: for one (scenario, seed) job, the initial model is trained once and
deep-copied into every policy's Session, so all policies start identical, see
the same observations with the same label delay and the same history. Each
policy has its own simulator, view, controller, monitor, registry and SQLite
run rows; nothing is shared after construction.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from amm.config import load_config
from amm.data import scenarios
from amm.engine import Session, train_initial
from amm.storage.store import Store

DETECTION_HORIZON_DAYS = 90


def _events(store: Store, run_id: str) -> pd.DataFrame:
    return store.query("SELECT step, ts, action, reason, fault_injection FROM decisions WHERE run_id=? ORDER BY event_id", (run_id,))


def daily_series(store: Store, run_id: str) -> pd.DataFrame:
    p = store.query(
        "SELECT batch, ts, y_true, y_pred, abs_err, scaled_err, model_version FROM predictions "
        "WHERE run_id=? AND role='active' AND y_true IS NOT NULL ORDER BY seq",
        (run_id,),
    )
    p["ts"] = pd.to_datetime(p["ts"])
    d = p.groupby("batch").agg(
        day=("ts", "first"), y=("y_true", "sum"), yhat=("y_pred", "sum"), mae=("abs_err", "mean"),
        sq=("abs_err", lambda s: float(np.mean(np.square(s)))), scaled=("scaled_err", "mean"), version=("model_version", "last"),
    )
    d["rmse"] = np.sqrt(d.pop("sq"))
    return d.reset_index()


def summarize_run(store: Store, s: Session, sc: scenarios.Scenario, wall: float) -> dict:
    rid = s.run_id
    p = store.query(
        "SELECT seq, ts, y_true, y_pred, abs_err, scaled_err FROM predictions WHERE run_id=? AND role='active' AND y_true IS NOT NULL",
        (rid,),
    )
    ev = _events(store, rid)
    cnt = ev["action"].value_counts()
    c = s.controller
    out = {
        "run_id": rid,
        "policy": s.policy,
        "scenario": sc.name,
        "kind": sc.kind,
        "seed": sc.manifest.get("seed"),
        "n_scored": int(len(p)),
        "unscored": int(store.query("SELECT COUNT(*) n FROM predictions WHERE run_id=? AND role='active' AND y_true IS NULL", (rid,))["n"][0]),
        "mae": float(p["abs_err"].mean()),
        "rmse": float(np.sqrt((p["abs_err"] ** 2).mean())),
        "scaled": float(p["scaled_err"].mean()),
        "bias": float(p["y_pred"].sum() / p["y_true"].sum() - 1),
        "cycles": int(c.cycle),
        "fits": int(c.fits),
        "train_seconds": round(float(c.train_seconds), 2),
        "wall_seconds": round(wall, 2),
        "promotions": int(cnt.get("PROMOTED", 0)),
        "rejections": int(cnt.get("CANDIDATES_REJECTED", 0)),
        "rollbacks": int(cnt.get("ROLLED_BACK", 0)),
        "kept": int(cnt.get("KEPT", 0)),
        "failed": int(cnt.get("TRAINING_FAILED", 0) + cnt.get("PROMOTION_FAILED", 0)),
        "alarms": int(cnt.get("ALARM", 0)),
        "confirmed": int(cnt.get("DETERIORATION_CONFIRMED", 0)),
        "dismissed": int(cnt.get("ALARM_DISMISSED", 0)),
        "declined_budget": int(cnt.get("RETRAIN_DECLINED", 0)),
        "final_version": c.registry.active_id,
    }
    ts = pd.to_datetime(p["ts"])
    out["mae_by_year"] = {str(k): round(float(v), 2) for k, v in p.groupby(ts.dt.year)["abs_err"].mean().items()}
    ch_seq = sc.change_seq()
    if ch_seq is not None:
        change_day = pd.Timestamp(sc.manifest["change"]["start"])
        out["change_start"] = str(change_day)
        out["change_end"] = sc.manifest["change"].get("end")
        post, pre = p[p["seq"] >= ch_seq], p[p["seq"] < ch_seq]
        out["mae_pre_change"] = float(pre["abs_err"].mean()) if len(pre) else None
        out["mae_post_change"] = float(post["abs_err"].mean())
        out["rmse_post_change"] = float(np.sqrt((post["abs_err"] ** 2).mean()))
        # post-change error inside the first 120 days, where adaptation matters most
        early = post[pd.to_datetime(post["ts"]) < change_day + pd.Timedelta(days=120)]
        out["mae_post_change_120d"] = float(early["abs_err"].mean())
        evd = ev.assign(day=pd.to_datetime(ev["ts"]))
        horizon = change_day + pd.Timedelta(days=DETECTION_HORIZON_DAYS)
        after = evd[(evd["day"] >= change_day) & (evd["day"] <= horizon)]

        def first(action):
            x = after[after["action"] == action]
            return int((x["day"].iloc[0] - change_day).days) if len(x) else None

        out["detect_delay_days"] = first("DETERIORATION_CONFIRMED")
        out["first_alarm_days"] = first("ALARM")
        out["first_retrain_days"] = first("RETRAIN_START")
        out["first_promotion_days"] = first("PROMOTED")
        out["missed_detection"] = s.policy == "adaptive" and out["detect_delay_days"] is None
    return out


def run_job(job: dict) -> list[dict]:
    """job: {config, overrides, scenario, seed, policies, out_dir}"""
    cfg = load_config(job.get("config"), job.get("overrides"))
    out_dir = Path(job["out_dir"])
    tag = job.get("tag", "")
    try:
        sc = scenarios.build(job["scenario"], cfg, job.get("seed"))
        init = train_initial(sc, cfg)
        results = []
        for policy in job["policies"]:
            seed_tag = f"-s{job['seed']}" if job.get("seed") is not None else ""
            rid = f"{tag}{policy}-{sc.name}{seed_tag}"
            db = out_dir / "runs" / f"{rid}.sqlite"
            if db.exists():
                db.unlink()
            store = Store(db)
            s = Session(sc, policy, cfg, store, run_id=rid, initial=init, artifact_root=out_dir / "artifacts")
            t0 = time.perf_counter()
            s.run()
            wall = time.perf_counter() - t0
            r = summarize_run(store, s, sc, wall)
            r["tag"] = tag
            r["overrides"] = json.dumps(job.get("overrides") or {})
            d = daily_series(store, rid)
            d.insert(0, "run_id", rid)
            (out_dir / "daily").mkdir(parents=True, exist_ok=True)
            d.to_csv(out_dir / "daily" / f"{rid}.csv", index=False)
            store.close()
            print(f"[run] {rid}: MAE={r['mae']:.2f} cycles={r['cycles']} promo={r['promotions']} rej={r['rejections']} "
                  f"rb={r['rollbacks']} train={r['train_seconds']:.0f}s wall={wall:.0f}s", flush=True)
            results.append(r)
        return results
    except Exception:
        traceback.print_exc()
        return [{"error": traceback.format_exc(), **{k: v for k, v in job.items() if k != "out_dir"}}]


def run_jobs(jobs: list[dict], workers: int = 1) -> list[dict]:
    if workers <= 1:
        res = [run_job(j) for j in jobs]
    else:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(run_job, jobs))
    return [r for rs in res for r in rs]
