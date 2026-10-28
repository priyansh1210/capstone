"""Multi-city evaluation: all policies x all scenarios, from a frozen code version.

Groups (configs/multicity.yaml):
  clean           Chicago, San Francisco, New York (+ injected abrupt copies) and DC 2025:
                  never used for any design decision -> the confirmatory test
  dc_exploratory  DC 2018-2024 (design decisions were informed by these years)
  generated       synthetic stationary / abrupt, 5 seeds

Outputs in reports/<name>/: results.csv/json, summary.csv/md, significance.csv,
ablations.csv, cities.csv, daily/, fig_pareto_clean.png, fig_rolling_*.png,
environment.json (incl. the git commit/tag the run used).
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from amm import paths
from amm.config import load_config
from amm.experiments import charts, stats
from amm.experiments.benchmark import counterfactual_effects, counterfactual_of
from amm.experiments.runner import run_jobs

COLS = ["mae", "rmse", "cycles", "fits", "compute_seconds", "train_seconds", "probes", "probe_seconds", "promotions", "rejections",
        "rollbacks", "alarms", "detect_delay_days", "first_retrain_days", "first_promotion_days", "mae_post_change_120d",
        "excess_scaled_120d", "recovery_days"]


def _git() -> dict:
    def g(*a):
        try:
            return subprocess.run(["git", *a], cwd=paths.ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ""

    return {"commit": g("rev-parse", "HEAD"), "describe": g("describe", "--tags", "--always", "--dirty"), "status_porcelain": g("status", "--porcelain")[:2000]}


def plan(cfg: dict, config_path: str, out: Path) -> list[dict]:
    m = cfg["multicity"]
    jobs = []
    for group, scs in m["groups"].items():
        for sc in scs:
            seeds = m["synthetic_seeds"] if sc.startswith("synthetic") else [None]
            specs = dict(m["policies"])
            if group == "clean" and sc.endswith("_unmodified"):
                specs.update(m["ablations"])
            for label, spec in specs.items():
                if spec.get("only_changed") and counterfactual_of(sc) is None:
                    continue
                for sd in seeds:
                    jobs.append({"config": config_path, "overrides": spec.get("overrides"), "scenario": sc, "seed": sd,
                                 "policies": [spec["policy"]], "label": label, "group": group, "out_dir": str(out), "tag": ""})

    def cost(j):  # longest first for better packing
        base = 0 if j["scenario"].startswith("synthetic") else 10
        per = {"periodic-14": 5, "periodic-28": 4, "periodic-56": 2}.get(j["label"], 1)
        return -(base + per)

    return sorted(jobs, key=cost)


def run(config_path: str = "configs/multicity.yaml", workers: int = 4, name: str = "multicity") -> Path:
    cfg = load_config(config_path)
    out = paths.REPORTS / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    jobs = plan(cfg, config_path, out)
    group_of = {(j["label"], j["scenario"], j["seed"]): j["group"] for j in jobs}
    print(f"[multicity] {len(jobs)} runs on {workers} workers", flush=True)
    t0 = time.perf_counter()
    res = run_jobs(jobs, workers)
    secs = time.perf_counter() - t0
    errors = [r for r in res if "error" in r]
    res = [r for r in res if "error" not in r]
    for r in res:
        seed = r.get("seed")
        r["group"] = group_of.get((r["label"], r["scenario"], None if seed is None or seed != seed else int(seed)), "?")
    (out / "results.json").write_text(json.dumps({"runs": res, "errors": errors}, indent=2, default=str))
    import river
    import sklearn

    env = {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor(),
           "numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": sklearn.__version__, "river": river.__version__,
           "runs": len(res), "failed_jobs": len(errors), "multicity_seconds": round(secs, 1), "git": _git(), "config": cfg}
    (out / "environment.json").write_text(json.dumps(env, indent=2, default=str))
    if errors:
        print(f"[multicity] {len(errors)} job(s) failed - see results.json", flush=True)
    report(out)
    return out


def _fmt(v, nd=1):
    return "-" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{nd}f}"


def report(out: Path) -> None:
    data = json.loads((out / "results.json").read_text())
    res = pd.DataFrame(data["runs"])
    if res.empty:
        return
    cfx = counterfactual_effects(res.assign(policy=res["label"]), out / "daily")
    res = res.drop(columns=[c for c in ("recovery_days", "excess_scaled_120d") if c in res]).merge(cfx, on="run_id", how="left")
    res.drop(columns=[c for c in res.columns if res[c].map(lambda v: isinstance(v, dict)).any()]).to_csv(out / "results.csv", index=False)
    g = res.groupby(["group", "scenario", "label"])
    summ = g[[c for c in COLS if c in res]].mean(numeric_only=True).join(g["mae"].std().rename("mae_sd")).join(g.size().rename("runs")).reset_index()
    summ.to_csv(out / "summary.csv", index=False)

    # ---- per-city table (clean group): MAE relative to static and to the 28-day schedule
    rows = []
    for sc, t in summ[summ["group"].isin(["clean", "dc_exploratory"])].groupby("scenario"):
        t = t.set_index("label")
        st, p28 = t.loc["static", "mae"], t.loc["periodic-28", "mae"]
        for lab, r in t.iterrows():
            rows.append({"group": r["group"], "scenario": sc, "label": lab, "mae": r["mae"], "vs_static": r["mae"] / st - 1,
                         "vs_periodic28": r["mae"] / p28 - 1, "cycles": r["cycles"], "compute_seconds": r["compute_seconds"],
                         "compute_vs_periodic28": r["compute_seconds"] / max(t.loc["periodic-28", "compute_seconds"], 1e-9)})
    cities = pd.DataFrame(rows)
    cities.to_csv(out / "cities.csv", index=False)

    # ---- paired significance on the same days
    daily = {r["run_id"]: pd.read_csv(out / "daily" / f"{r['run_id']}.csv", parse_dates=["day"]) for _, r in res.iterrows()
             if (out / "daily" / f"{r['run_id']}.csv").exists()}
    cfg = json.loads((out / "environment.json").read_text())["config"] if (out / "environment.json").exists() else {}
    pairs = (cfg.get("multicity") or {}).get("comparisons", [["probe", "periodic-28"], ["probe", "adaptive"], ["probe", "static"]])
    sig = []
    for (sc, seed), t in res.groupby(["scenario", res["seed"].fillna(-1)]):
        by = t.set_index("label")
        for a, b in pairs:
            if a in by.index and b in by.index and by.loc[a, "run_id"] in daily and by.loc[b, "run_id"] in daily:
                r = stats.paired(daily[by.loc[a, "run_id"]], daily[by.loc[b, "run_id"]])
                sig.append({"group": by.loc[a, "group"], "scenario": sc, "seed": None if seed == -1 else int(seed), "a": a, "b": b, **r})
    sig = pd.DataFrame(sig)
    sig.to_csv(out / "significance.csv", index=False)

    # ---- ablations (clean unmodified)
    abl = summ[(summ["group"] == "clean") & summ["scenario"].str.endswith("_unmodified")
               & summ["label"].isin(["probe", "probe-no-accel", "probe-no-test", "probe-no-probation", "adaptive", "adaptive-no-seasonal", "adaptive-no-warmstart"])]
    abl[["scenario", "label", "mae", "rmse", "cycles", "compute_seconds", "probes", "promotions", "rollbacks"]].to_csv(out / "ablations.csv", index=False)

    _figures(out, res, summ)
    _summary_md(out, summ, cities, sig, abl, data.get("errors", []))


def _figures(out: Path, res: pd.DataFrame, summ: pd.DataFrame) -> None:
    clean_un = [s for s in summ.loc[summ["group"] == "clean", "scenario"].unique() if s.endswith("_unmodified")]
    dc = [s for s in ("bike_unmodified",) if s in set(summ["scenario"])]
    panels = clean_un + dc
    if panels:
        charts.pareto(summ[summ["scenario"].isin(panels)], panels, out / "fig_pareto_clean.png",
                      "Prediction error vs compute (training + probes): clean cities and DC (exploratory)")
    for sc in panels + [s for s in summ["scenario"].unique() if s.endswith("_abrupt") and not s.startswith("synthetic")]:
        sel = res[(res["scenario"] == sc) & res["label"].isin(["static", "periodic-28", "adaptive", "probe"])]
        d = {r["label"]: pd.read_csv(out / "daily" / f"{r['run_id']}.csv", parse_dates=["day"]) for _, r in sel.iterrows()
             if (out / "daily" / f"{r['run_id']}.csv").exists()}
        if d:
            row = sel.iloc[0]
            ch = {"start": row.get("change_start"), "end": row.get("change_end")} if isinstance(row.get("change_start"), str) else None
            if ch and not isinstance(ch["end"], str):
                ch["end"] = None
            charts.rolling_multi(d, f"{sc} - rolling MAE (28-day)", out / f"fig_rolling_{sc}.png", ch)


def _summary_md(out, summ, cities, sig, abl, errors) -> None:
    L = ["# Multi-city evaluation", "",
         "MAE in trips/hour. `clean` = never used for design decisions (confirmatory). "
         "Compute = measured training + probe seconds. Negative 'vs' = lower error.", ""]
    for grp in ("clean", "dc_exploratory"):
        c = cities[cities["group"] == grp]
        if c.empty:
            continue
        L += [f"## {grp}: MAE relative to static and to periodic-28", "", "| scenario | policy | MAE | vs static | vs periodic-28 | cycles | compute s | compute vs p28 |", "|---|---|---|---|---|---|---|---|"]
        for _, r in c.sort_values(["scenario", "mae"]).iterrows():
            L.append(f"| {r['scenario']} | {r['label']} | {_fmt(r['mae'])} | {r['vs_static']:+.1%} | {r['vs_periodic28']:+.1%} | {_fmt(r['cycles'])} | {_fmt(r['compute_seconds'])} | {r['compute_vs_periodic28']:.2f}x |")
        mean = c.groupby("label")[["vs_static", "vs_periodic28", "compute_vs_periodic28"]].mean().sort_values("vs_periodic28")
        L += ["", f"Mean over {grp} scenarios:", "", "| policy | vs static | vs periodic-28 | compute vs p28 |", "|---|---|---|---|"]
        L += [f"| {lab} | {r['vs_static']:+.1%} | {r['vs_periodic28']:+.1%} | {r['compute_vs_periodic28']:.2f}x |" for lab, r in mean.iterrows()]
        L.append("")
    if len(sig):
        L += ["## Paired tests (daily MAE, A - B; block-bootstrap 95 % CI; Diebold-Mariano)", "",
              "| group | scenario | seed | A | B | days | MAE A | MAE B | diff | 95 % CI | DM p |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in sig.sort_values(["group", "scenario", "a", "b"]).iterrows():
            L.append(f"| {r['group']} | {r['scenario']} | {'' if pd.isna(r['seed']) else int(r['seed'])} | {r['a']} | {r['b']} | {r['n_days']} | {_fmt(r['mae_a'])} | {_fmt(r['mae_b'])} | "
                     f"{r['diff']:+.2f} | [{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] | {_fmt(r['dm_p'], 3)} |")
        L.append("")
    if len(abl):
        L += ["## Ablations (clean unmodified)", "", "| scenario | variant | MAE | cycles | compute s | probes | rollbacks |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['scenario']} | {r['label']} | {_fmt(r['mae'])} | {_fmt(r['cycles'])} | {_fmt(r['compute_seconds'])} | {_fmt(r['probes'], 0)} | {_fmt(r['rollbacks'])} |"
              for _, r in abl.sort_values(["scenario", "label"]).iterrows()]
        L.append("")
    gen = summ[summ["group"] == "generated"]
    if len(gen):
        L += ["## Generated scenarios (mean over seeds)", "", "| scenario | policy | MAE (sd) | cycles | compute s | detect d | first retrain d |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['scenario']} | {r['label']} | {_fmt(r['mae'])} ({_fmt(r['mae_sd'])}) | {_fmt(r['cycles'])} | {_fmt(r['compute_seconds'])} | {_fmt(r['detect_delay_days'])} | {_fmt(r['first_retrain_days'])} |"
              for _, r in gen.sort_values(["scenario", "mae"]).iterrows()]
        L.append("")
    if errors:
        L += [f"**{len(errors)} job(s) failed** - see results.json.", ""]
    (out / "summary.md").write_text("\n".join(L))
