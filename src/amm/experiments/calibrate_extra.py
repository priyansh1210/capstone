"""Calibrate the new pieces on DEVELOPMENT scenarios only, then freeze them.

* probe policy (proposed method): probe interval x challenger window
* Page-Hinkley and KSWIN as alternative drift detectors for the adaptive baseline

Same development scenarios and selection rule as `calibrate` (lowest mean MAE
ratio vs static; at most 1 retraining cycle on average on the stationary dev
streams; ties within 1 % -> fewer cycles). The chosen values are added to
configs/frozen_policy.yaml (existing values are not touched).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import yaml

from amm import paths
from amm.config import load_config
from amm.experiments.calibrate import _jobs, _key
from amm.experiments.runner import run_jobs

GRID = {
    "probe": [{"interval_batches": i, "window_days": w} for i in (7, 14) for w in (120, 365)],
    "page_hinkley": [{"threshold": t} for t in (5.0, 10.0, 20.0)],
    "kswin": [{"alpha": a, "window_size": 200, "stat_size": 50} for a in (0.0001, 0.001, 0.005)],
}


def _overrides(family: str, params: dict) -> tuple[str, dict]:
    base = {"storage": {"persist_artifacts": False}}
    if family == "probe":
        return "probe", {**base, "probe": params}
    return "adaptive", {**base, "monitor": {"detector": family, "detector_params": params}}


def _pick(rows: list[dict]) -> dict:
    t = pd.DataFrame(rows)
    feas = t[t["stationary_cycles"] <= 1.0]
    pool = feas if len(feas) else t
    best = pool["mae_ratio"].min()
    return pool[pool["mae_ratio"] <= best * 1.01].sort_values(["cycles", "mae_ratio"]).iloc[0].to_dict()


def run(workers: int = 4) -> dict:
    base = load_config()
    out = paths.REPORTS / "calibration_extra"
    out.mkdir(parents=True, exist_ok=True)
    static = run_jobs(_jobs(base, ["static"], {"storage": {"persist_artifacts": False}}, "cx-static-", out), workers)
    static_mae = {_key(r): r["mae"] for r in static}
    jobs, index = [], []
    for fam, configs in GRID.items():
        for i, params in enumerate(configs):
            policy, ov = _overrides(fam, params)
            tag = f"cx-{fam}{i}-"
            jobs += _jobs(base, [policy], ov, tag, out)
            index.append((fam, i, params, tag))
    res = run_jobs(jobs, workers)
    tables, chosen = {}, {}
    for fam, i, params, tag in index:
        rs = [r for r in res if r.get("tag") == tag and "error" not in r]
        stat = [r for r in rs if r["scenario"] == "synthetic_stationary"]
        row = {**params, "mae_ratio": sum(r["mae"] / static_mae[_key(r)] for r in rs) / len(rs),
               "cycles": sum(r["cycles"] for r in rs) / len(rs), "stationary_cycles": sum(r["cycles"] for r in stat) / len(stat),
               "probes": sum(r.get("probes", 0) for r in rs) / len(rs)}
        tables.setdefault(fam, []).append(row)
    for fam, rows in tables.items():
        pick = _pick(rows)
        chosen[fam] = {k: (int(v) if k in ("interval_batches", "window_days", "window_size", "stat_size") else float(v))
                       for k, v in pick.items() if k in GRID[fam][0]}
        print(f"[calibrate-extra] {fam}:\n{pd.DataFrame(rows).round(4).to_string()}\n -> {chosen[fam]}", flush=True)

    fp = paths.CONFIGS / "frozen_policy.yaml"
    frozen = yaml.safe_load(fp.read_text()) if fp.exists() else {"provenance": {}, "values": {}}
    frozen["values"]["probe"] = chosen["probe"]
    frozen["values"]["detectors"] = {"page_hinkley": chosen["page_hinkley"], "kswin": chosen["kswin"]}
    frozen["provenance"]["extra"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": "amm calibrate-extra on development scenarios only (same rule as calibrate)",
        "grids": tables,
    }
    fp.write_text(yaml.safe_dump(frozen, sort_keys=False))
    (out / "calibration_extra_summary.json").write_text(json.dumps({"chosen": chosen, "grids": tables}, indent=2, default=float))
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in res]).to_csv(out / "runs.csv", index=False)
    return {"chosen": chosen, "grids": tables}
