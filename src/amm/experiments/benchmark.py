"""Benchmark: static vs periodic vs adaptive on every evaluation scenario.

Writes to reports/<name>/:
  results.csv / results.json   one row per (policy, scenario, seed) run
  summary.csv / summary.md     mean (and sd over seeds) per policy x scenario
  daily/*.csv                  per-run daily MAE series
  runs/*.sqlite                full per-run records (predictions, decisions, versions)
  fig_*.png                    charts generated from these files
  environment.json             versions, machine, config snapshot, runtime
"""

from __future__ import annotations

import json
import platform
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from amm import paths
from amm.config import load_config
from amm.experiments import charts
from amm.experiments.runner import run_jobs

COLS = ["mae", "rmse", "scaled", "cycles", "fits", "train_seconds", "wall_seconds", "promotions", "rejections", "rollbacks",
        "alarms", "confirmed", "dismissed", "mae_post_change", "mae_post_change_120d", "detect_delay_days", "first_promotion_days",
        "recovery_days", "excess_scaled_120d"]


def _env(cfg: dict, seconds: float) -> dict:
    import river
    import sklearn

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit-learn": sklearn.__version__,
        "river": river.__version__,
        "benchmark_seconds": round(seconds, 1),
        "config": cfg,
    }


def run(config_path: str, workers: int = 4, name: str = "benchmark") -> Path:
    cfg = load_config(config_path)
    b = cfg["benchmark"]
    out = paths.REPORTS / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    jobs = []
    for sc in b["scenarios"]:
        seeds = b["synthetic_seeds"] if sc.startswith("synthetic") else [None]
        for sd in seeds:
            jobs.append({"config": config_path, "overrides": None, "scenario": sc, "seed": sd, "policies": b["policies"], "out_dir": str(out), "tag": ""})
    # longest jobs first for better packing
    jobs.sort(key=lambda j: 0 if j["scenario"].startswith("bike") else 1)
    t0 = time.perf_counter()
    res = run_jobs(jobs, workers)
    secs = time.perf_counter() - t0
    errors = [r for r in res if "error" in r]
    res = [r for r in res if "error" not in r]
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in res]).to_csv(out / "results.csv", index=False)
    (out / "results.json").write_text(json.dumps({"runs": res, "errors": errors}, indent=2, default=str))
    (out / "environment.json").write_text(json.dumps(_env(cfg, secs), indent=2, default=str))
    if errors:
        print(f"[benchmark] {len(errors)} job(s) failed - see results.json")
    report(out)
    return out


COUNTERFACTUAL = {"bike_abrupt": "bike_unmodified", "bike_gradual": "bike_unmodified", "synthetic_abrupt": "synthetic_stationary"}
RECOVERY_TOL, RECOVERY_HOLD, ROLL = 0.10, 14, 14


def counterfactual_effects(res: pd.DataFrame, daily_dir: Path) -> pd.DataFrame:
    """Excess error caused by the injected change, against the same policy on
    the same stream without the change (bike: unmodified replay; synthetic:
    same-seed stationary stream, whose noise draws are identical).

    Uses the daily mean *scaled* (log) error, which a perfectly re-adapted
    model would bring back to the counterfactual level under a multiplicative
    change (absolute errors grow with demand even then).

    recovery_days: days after the change is complete (start, or end of the
    ramp) until the 14-day rolling excess stays <= 10 % for 14 consecutive
    days; NaN = criterion never met. excess_120d: mean excess over the first
    120 days after the change is complete.
    """
    rows = []
    for _, r in res[res["scenario"].isin(COUNTERFACTUAL)].iterrows():
        cf = res[(res["scenario"] == COUNTERFACTUAL[r["scenario"]]) & (res["policy"] == r["policy"])]
        if r["seed"] == r["seed"]:  # not NaN
            cf = cf[cf["seed"] == r["seed"]]
        f1, f0 = daily_dir / f"{r['run_id']}.csv", daily_dir / f"{cf['run_id'].iloc[0]}.csv" if len(cf) else None
        if f0 is None or not f1.exists() or not f0.exists():
            continue
        d1 = pd.read_csv(f1, parse_dates=["day"]).set_index("day")["scaled"]
        d0 = pd.read_csv(f0, parse_dates=["day"]).set_index("day")["scaled"]
        ratio = (d1.rolling(ROLL).mean() / d0.rolling(ROLL).mean() - 1).dropna()
        t0 = pd.Timestamp(r["change_end"]) if isinstance(r.get("change_end"), str) else pd.Timestamp(r["change_start"])
        post = ratio[ratio.index >= t0 + pd.Timedelta(days=ROLL)]
        ok = (post <= RECOVERY_TOL).to_numpy()
        rec = np.nan
        for i in range(len(ok) - RECOVERY_HOLD + 1):
            if ok[i : i + RECOVERY_HOLD].all():
                rec = float((post.index[i] - t0).days)
                break
        exc = (d1 / d0 - 1)[(d1.index >= t0) & (d1.index < t0 + pd.Timedelta(days=120))]
        rows.append({"run_id": r["run_id"], "recovery_days": rec, "excess_scaled_120d": float(exc.mean())})
    return pd.DataFrame(rows, columns=["run_id", "recovery_days", "excess_scaled_120d"])


def report(out: Path) -> None:
    data = json.loads((out / "results.json").read_text())
    res = pd.DataFrame(data["runs"])
    if res.empty:
        return
    res = res.drop(columns=[c for c in ("recovery_days", "recovery_baseline_signal", "excess_scaled_120d") if c in res])
    cfx = counterfactual_effects(res, out / "daily")
    res = res.merge(cfx, on="run_id", how="left") if len(cfx) else res.assign(recovery_days=np.nan, excess_scaled_120d=np.nan)
    res.drop(columns=[c for c in res.columns if isinstance(res[c].iloc[0], dict)]).to_csv(out / "results.csv", index=False)
    g = res.groupby(["scenario", "policy"])
    mean = g[[c for c in COLS if c in res]].mean(numeric_only=True)
    rec_met = g["recovery_days"].apply(lambda x: f"{int(x.notna().sum())}/{len(x)}").rename("recovered_runs")
    sd = g[["mae", "rmse"]].std()
    n = g.size().rename("runs")
    summ = mean.join(sd, rsuffix="_sd").join(n).join(rec_met).reset_index()
    summ.to_csv(out / "summary.csv", index=False)
    _summary_md(summ, res, out)

    # charts: rolling error for each scenario (synthetic: first seed)
    daily_dir = out / "daily"
    for sc, grp in res.groupby("scenario"):
        first_seed = grp["seed"].dropna().min() if grp["seed"].notna().any() else None
        sel = grp if first_seed is None else grp[grp["seed"] == first_seed]
        daily = {}
        for _, r in sel.iterrows():
            f = daily_dir / f"{r['run_id']}.csv"
            if f.exists():
                daily[r["policy"]] = pd.read_csv(f, parse_dates=["day"])
        row = sel.iloc[0]
        cs = row.get("change_start") if "change_start" in sel else None
        change = {"start": cs, "end": row.get("change_end")} if isinstance(cs, str) else None
        if change and not isinstance(change["end"], str):
            change["end"] = None
        events = [("COVID-19 (Mar 2020)", "2020-03-15")] if sc.startswith("bike") else None
        label = {"bike_unmodified": "source observations", "bike_abrupt": "modified observations", "bike_gradual": "modified observations"}.get(sc, "generated data")
        seed_txt = f", seed {int(first_seed)}" if first_seed is not None else ""
        charts.rolling_error(daily, f"{sc} ({label}{seed_txt}) - rolling MAE by policy", out / f"fig_rolling_{sc}.png", change, events=events)
    charts.tradeoff(summ, out / "fig_tradeoff.png")
    yr = res[res["scenario"] == "bike_unmodified"]
    if len(yr):
        charts.yearly({r["policy"]: r["mae_by_year"] for _, r in yr.iterrows()}, out / "fig_yearly_bike_unmodified.png",
                      "bike_unmodified (source observations) - MAE per year")


def _fmt(v, nd=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:.{nd}f}"


def _summary_md(summ: pd.DataFrame, res: pd.DataFrame, out: Path) -> None:
    lines = ["| scenario | policy | runs | MAE (sd) | RMSE | cycles | fits | train s | promo | reject | rollback | detect delay d | post-change MAE (120 d) | excess log-error vs no-change (120 d) | recovery d (runs met) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in summ.iterrows():
        sdv = r.get("mae_sd")
        mae_txt = _fmt(r["mae"]) + (f" ({_fmt(sdv)})" if r["runs"] > 1 else "")
        lines.append(
            f"| {r['scenario']} | {r['policy']} | {int(r['runs'])} | {mae_txt} | {_fmt(r['rmse'])} | {_fmt(r['cycles'])} | {_fmt(r['fits'], 0)} | "
            f"{_fmt(r['train_seconds'])} | {_fmt(r['promotions'])} | {_fmt(r['rejections'])} | {_fmt(r['rollbacks'])} | "
            f"{_fmt(r['detect_delay_days'])} | {_fmt(r['mae_post_change_120d'])} | "
            f"{(_fmt(100 * r['excess_scaled_120d'], 0) + ' %') if r['excess_scaled_120d'] == r['excess_scaled_120d'] else '-'} | "
            f"{(_fmt(r['recovery_days'], 0) + ' (' + r['recovered_runs'] + ')') if r['scenario'] in COUNTERFACTUAL else 'n/a'} |"
        )
    miss = res[(res["policy"] == "adaptive") & res.get("missed_detection", pd.Series(False, index=res.index)).fillna(False).astype(bool)]
    lines.append("")
    lines.append(f"Missed detections (adaptive, injected-change scenarios, {90}-day horizon): {len(miss)} run(s).")
    lines.append("Recovery: days after the change is complete until the 14-day rolling log-error is within 10 % of the same policy on the "
                 "no-change counterfactual stream for 14 consecutive days; '-' = never met (count of runs that met it in brackets; mean over those).")
    (out / "summary.md").write_text("\n".join(lines))
