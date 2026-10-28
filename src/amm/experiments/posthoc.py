"""POST-HOC analysis: an adaptive variant designed AFTER seeing the frozen benchmark.

Diagnosis from the frozen run's decision log (bike_unmodified, adaptive): a model
promoted on 2020-03-29 passed probation during the COVID-19 collapse, its reference
was rebased to ~4x the normal error level, and every later alarm for 2.5 years was
dismissed while its error kept growing (MAE 332 by Sep 2022). A second weakness: a
deterioration trigger compares a model with its *own* reference, so after a partial
adaptation it cannot see that a better model has become attainable.

Variant ("adaptive+"): (1) reference cap at k x the initial model's calibration error
level, (2) a total-demand bias trigger. Parameters are chosen on the DEVELOPMENT
scenarios with the same rule as `calibrate` (lowest mean MAE ratio vs static, at most
1 cycle on average on stationary dev streams, ties within 1 % -> fewer cycles), then
the variant is run once on the evaluation scenarios. Because the idea came from the
evaluation data, the evaluation numbers are exploratory, not a clean test.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

import pandas as pd

from amm import paths
from amm.config import load_config
from amm.experiments.benchmark import counterfactual_effects
from amm.experiments.calibrate import _jobs, _key
from amm.experiments.runner import run_jobs

GRID = [(cap, bias) for cap in (None, 1.5, 2.0) for bias in (None, 0.10, 0.15)]


def run(workers: int = 4, name: str = "posthoc", bench: str = "benchmark") -> dict:
    base = load_config("configs/full.yaml")
    out = paths.REPORTS / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    noart = {"storage": {"persist_artifacts": False}}

    # ---- stage A: development scenarios only
    static = run_jobs(_jobs(base, ["static"], noart, "dev-static-", out), workers)
    static_mae = {_key(r): r["mae"] for r in static}
    jobs = []
    for i, (cap, bias) in enumerate(GRID):
        ov = {**noart, "policy": {"reference_cap_factor": cap, "bias_trigger": bias}}
        jobs += _jobs(base, ["adaptive"], ov, f"dev-g{i}-", out)
    res = run_jobs(jobs, workers)
    table = []
    for i, (cap, bias) in enumerate(GRID):
        rs = [r for r in res if r.get("tag") == f"dev-g{i}-"]
        stat = [r for r in rs if r["scenario"] == "synthetic_stationary"]
        table.append({"reference_cap_factor": cap, "bias_trigger": bias,
                      "mae_ratio": sum(r["mae"] / static_mae[_key(r)] for r in rs) / len(rs),
                      "cycles": sum(r["cycles"] for r in rs) / len(rs),
                      "stationary_cycles": sum(r["cycles"] for r in stat) / len(stat)})
    t = pd.DataFrame(table)
    feas = t[t["stationary_cycles"] <= 1.0]
    pool = feas if len(feas) else t
    best = pool["mae_ratio"].min()
    pick = pool[pool["mae_ratio"] <= best * 1.01].sort_values(["cycles", "mae_ratio"]).iloc[0]
    cap = None if pd.isna(pick["reference_cap_factor"]) else float(pick["reference_cap_factor"])
    bias = None if pd.isna(pick["bias_trigger"]) else float(pick["bias_trigger"])
    print("[posthoc] dev grid:\n", t.round(4).to_string(), f"\n-> cap={cap} bias={bias}", flush=True)

    # ---- stage B: evaluation scenarios, adaptive+ only (static/periodic/adaptive come from the frozen benchmark)
    ov = {**noart, "policy": {"reference_cap_factor": cap, "bias_trigger": bias}}
    b = base["benchmark"]
    ejobs = []
    for sc in b["scenarios"]:
        for sd in (b["synthetic_seeds"] if sc.startswith("synthetic") else [None]):
            ejobs.append({"config": "configs/full.yaml", "overrides": ov, "scenario": sc, "seed": sd, "policies": ["adaptive"],
                          "out_dir": str(out), "tag": "posthoc-"})
    ev = [r for r in run_jobs(ejobs, workers) if "error" not in r]
    for r in ev:
        r["policy"] = "adaptive+ (post-hoc)"
    main = json.loads((paths.REPORTS / bench / "results.json").read_text())["runs"]
    allr = pd.DataFrame(main + ev)
    daily = out / "daily"
    for r in main:  # counterfactual pairs need the frozen runs' daily series too
        src = paths.REPORTS / bench / "daily" / f"{r['run_id']}.csv"
        if src.exists():
            shutil.copy(src, daily / src.name)
    cfx = counterfactual_effects(allr, daily)
    allr = allr.merge(cfx, on="run_id", how="left")
    cols = ["mae", "rmse", "cycles", "fits", "train_seconds", "promotions", "rejections", "rollbacks", "detect_delay_days",
            "mae_post_change_120d", "excess_scaled_120d", "recovery_days"]
    comp = allr.groupby(["scenario", "policy"])[cols].mean(numeric_only=True).round(2).reset_index()
    comp.to_csv(out / "comparison.csv", index=False)
    yearly = {r["policy"]: r["mae_by_year"] for r in main + ev if r["scenario"] == "bike_unmodified"}
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "POST-HOC / exploratory: designed after inspecting the frozen evaluation; confirm on untouched data",
        "dev_grid": table,
        "chosen": {"reference_cap_factor": cap, "bias_trigger": bias},
        "bike_unmodified_mae_by_year": yearly,
    }
    (out / "posthoc_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    (out / "results.json").write_text(json.dumps({"runs": ev}, indent=2, default=str))
    lines = ["# Post-hoc variant vs frozen benchmark (exploratory)", "",
             f"Variant: reference cap = {cap}, bias trigger = {bias} (chosen on development scenarios).", "",
             "| scenario | policy | MAE | RMSE | cycles | train s | promo | reject | rollback | detect d | excess log-err 120 d | recovery d |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    def fmt(v, nd=1):
        return "-" if pd.isna(v) else f"{v:.{nd}f}"

    for _, r in comp.iterrows():
        exc = "-" if pd.isna(r["excess_scaled_120d"]) else f"{100 * r['excess_scaled_120d']:.0f} %"
        lines.append(f"| {r['scenario']} | {r['policy']} | {fmt(r['mae'])} | {fmt(r['rmse'])} | {fmt(r['cycles'])} | {fmt(r['train_seconds'])} | "
                     f"{fmt(r['promotions'])} | {fmt(r['rejections'])} | {fmt(r['rollbacks'])} | {fmt(r['detect_delay_days'])} | "
                     f"{exc} | {fmt(r['recovery_days'], 0)} |")
    (out / "comparison.md").write_text("\n".join(lines))
    figures(out, bench)
    return summary


def figures(out, bench: str = "benchmark") -> None:
    """Trade-off chart with the post-hoc variant and the real-replay rolling error."""
    from amm.experiments import charts

    comp = pd.read_csv(out / "comparison.csv")
    charts.tradeoff(comp, out / "fig_tradeoff_posthoc.png")
    main = pd.DataFrame(json.loads((paths.REPORTS / bench / "results.json").read_text())["runs"])
    ev = pd.DataFrame(json.loads((out / "results.json").read_text())["runs"])
    daily = {}
    for df in (main, ev):
        for _, r in df[df["scenario"] == "bike_unmodified"].iterrows():
            f = out / "daily" / f"{r['run_id']}.csv"
            if f.exists():
                daily[r["policy"]] = pd.read_csv(f, parse_dates=["day"])
    charts.rolling_error(daily, "bike_unmodified (source observations) - frozen policies + post-hoc variant (dashed)",
                         out / "fig_rolling_bike_unmodified_posthoc.png", events=[("COVID-19 (Mar 2020)", "2020-03-15")])
