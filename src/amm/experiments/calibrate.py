"""Calibrate policy settings on DEVELOPMENT scenarios only, then freeze them.

Development scenarios (configs/base.yaml: dev):
  dev_bike_unmodified / dev_bike_abrupt / dev_bike_gradual: train 2011-2014,
  calibration 2015, replay 2016-2017 (ends before the evaluation replay
  starts in 2018); dev changes differ from evaluation changes.
  synthetic_stationary with dev seeds (101-103, evaluation uses 1-5).

Stage 1  candidate training windows (shared by periodic and adaptive):
         lowest mean MAE ratio vs static over dev scenarios, both policies.
Stage 2  adaptive: ADWIN delta x deterioration rel_margin. Constraint: at most
         1 retraining cycle on average on the stationary dev streams
         (unnecessary retraining); objective: lowest mean MAE ratio vs static;
         ties within 1 % -> fewer cycles.
Stage 3  periodic interval: lowest mean MAE ratio; ties within 1 % -> longer
         interval (cheaper).
Results are written to reports/calibration/ and configs/frozen_policy.yaml.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import yaml

from amm import paths
from amm.config import load_config
from amm.experiments.runner import run_jobs

DEV_BIKE = ["dev_bike_unmodified", "dev_bike_abrupt", "dev_bike_gradual"]


def _jobs(cfg, policies, overrides, tag, out_dir):
    jobs = [{"config": None, "overrides": overrides, "scenario": s, "seed": None, "policies": policies, "out_dir": str(out_dir), "tag": tag} for s in DEV_BIKE]
    jobs += [
        {"config": None, "overrides": overrides, "scenario": "synthetic_stationary", "seed": sd, "policies": policies, "out_dir": str(out_dir), "tag": tag}
        for sd in cfg["dev"]["synthetic_seeds"]
    ]
    return jobs


def _key(r):
    return f"{r['scenario']}|{r.get('seed')}"


def run(workers: int = 4, grid: dict | None = None) -> dict:
    base = load_config(overrides={"frozen_policy_file": None})  # calibrate from base values
    grid = grid or {
        "windows": [[56, 365], [365, 730]],
        "adwin_delta": [0.002, 0.02],
        "rel_margin": [0.15, 0.3, 0.5],
        "interval": [14, 28, 56, 91],
    }
    out = paths.REPORTS / "calibration"
    out.mkdir(parents=True, exist_ok=True)
    noart = {"storage": {"persist_artifacts": False}, "frozen_policy_file": None}
    rows = []

    # static reference per dev scenario
    static = run_jobs(_jobs(base, ["static"], noart, "cal-static-", out), workers)
    static_mae = {_key(r): r["mae"] for r in static}
    rows += [dict(r, stage="static") for r in static]

    def ratio(rs):
        return sum(r["mae"] / static_mae[_key(r)] for r in rs) / len(rs)

    # ---- stage 1: windows
    jobs = []
    for i, w in enumerate(grid["windows"]):
        ov = {**noart, "retraining": {"windows_days": w}}
        jobs += _jobs(base, ["periodic", "adaptive"], ov, f"cal-w{i}-", out)
    res = run_jobs(jobs, workers)
    rows += [dict(r, stage="windows") for r in res]
    w_scores = {}
    for i, w in enumerate(grid["windows"]):
        rs = [r for r in res if r.get("tag") == f"cal-w{i}-"]
        w_scores[str(w)] = ratio(rs)
    best_w = json.loads(min(w_scores, key=w_scores.get))
    print("[calibrate] windows:", w_scores, "->", best_w)

    # ---- stage 2: adaptive thresholds
    jobs = []
    combos = [(d, m) for d in grid["adwin_delta"] for m in grid["rel_margin"]]
    for i, (d, m) in enumerate(combos):
        ov = {**noart, "retraining": {"windows_days": best_w}, "monitor": {"adwin_delta": d}, "policy": {"deterioration": {"rel_margin": m}}}
        jobs += _jobs(base, ["adaptive"], ov, f"cal-a{i}-", out)
    res = run_jobs(jobs, workers)
    rows += [dict(r, stage="adaptive") for r in res]
    a_table = []
    for i, (d, m) in enumerate(combos):
        rs = [r for r in res if r.get("tag") == f"cal-a{i}-"]
        stat = [r for r in rs if r["scenario"] == "synthetic_stationary"]
        a_table.append(
            {"adwin_delta": d, "rel_margin": m, "mae_ratio": ratio(rs), "cycles": sum(r["cycles"] for r in rs) / len(rs),
             "stationary_cycles": sum(r["cycles"] for r in stat) / len(stat)}
        )
    at = pd.DataFrame(a_table)
    feas = at[at["stationary_cycles"] <= 1.0]
    pool = feas if len(feas) else at
    bestr = pool["mae_ratio"].min()
    pick = pool[pool["mae_ratio"] <= bestr * 1.01].sort_values(["cycles", "mae_ratio"]).iloc[0]
    print("[calibrate] adaptive grid:\n", at.round(4).to_string(), "\n->", dict(pick))

    # ---- stage 3: periodic interval
    jobs = []
    for i, iv in enumerate(grid["interval"]):
        ov = {**noart, "retraining": {"windows_days": best_w}, "policy": {"periodic_interval_batches": iv}}
        jobs += _jobs(base, ["periodic"], ov, f"cal-p{i}-", out)
    res = run_jobs(jobs, workers)
    rows += [dict(r, stage="periodic") for r in res]
    p_table = []
    for i, iv in enumerate(grid["interval"]):
        rs = [r for r in res if r.get("tag") == f"cal-p{i}-"]
        p_table.append({"interval": iv, "mae_ratio": ratio(rs), "cycles": sum(r["cycles"] for r in rs) / len(rs)})
    pt = pd.DataFrame(p_table)
    bestp = pt["mae_ratio"].min()
    ppick = pt[pt["mae_ratio"] <= bestp * 1.01].sort_values("interval", ascending=False).iloc[0]
    print("[calibrate] periodic grid:\n", pt.round(4).to_string(), "\n->", dict(ppick))

    frozen = {
        "provenance": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": __doc__.strip().splitlines()[0],
            "dev_scenarios": DEV_BIKE + [f"synthetic_stationary seeds {base['dev']['synthetic_seeds']}"],
            "window_scores_mae_ratio": w_scores,
            "adaptive_grid": a_table,
            "periodic_grid": p_table,
        },
        "values": {
            "retraining": {"windows_days": best_w},
            "monitor": {"adwin_delta": float(pick["adwin_delta"])},
            "policy": {"deterioration": {"rel_margin": float(pick["rel_margin"])}, "periodic_interval_batches": int(ppick["interval"])},
        },
    }
    (paths.CONFIGS / "frozen_policy.yaml").write_text(yaml.safe_dump(frozen, sort_keys=False))
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in rows]).to_csv(out / "calibration_runs.csv", index=False)
    (out / "calibration_summary.json").write_text(json.dumps(frozen, indent=2, default=float))
    return frozen
