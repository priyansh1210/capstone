"""Cost model over executed results: which policy is cheapest for a given price of retraining?

Reporting only - it re-weights the pre-registered results and tunes nothing. For each stream
and policy p:

    J(p; kappa) = MAE_p / MAE_periodic-28 + kappa * effective_cycles_p / replay_days

``kappa`` is the price of one full retraining cycle in *days of forecast error at the 28-day
schedule's average level* (kappa = 2: one cycle costs as much as two days of that error).
``effective_cycles`` counts probes at their measured compute share of a cycle on the same
stream (about 8 %), the conservative choice; if the price of a cycle is human sign-off or
deployment risk rather than compute, probes cost nothing and the probe policy only gains.
Regret = J - min over policies of J on that stream, in units of periodic-28's MAE. kappa is
swept, never chosen.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from amm.experiments import charts

POLICIES = ["static", "periodic-14", "periodic-28", "periodic-56", "periodic-91", "adaptive", "adaptive-ph", "adaptive-kswin", "adaptive-bias", "probe"]
KAPPAS = np.r_[0.0, np.logspace(-2, 2, 81)]
TABLE_KAPPAS = [0, 0.5, 1, 2, 5, 10, 20, 50]
SETS = {"clean": "clean real streams (7)", "synthetic_stationary": "generated stationary (5 seeds)", "synthetic_abrupt": "generated abrupt (5 seeds)"}


def stream_terms(res: pd.DataFrame) -> pd.DataFrame:
    """Per stream and policy: MAE relative to periodic-28 and effective cycles per replay day."""
    rows = []
    for (sc, seed), t in res.groupby(["scenario", res["seed"].fillna(-1)]):
        t = t[t["label"].isin(POLICIES)].set_index("label")
        if "periodic-28" not in t.index:
            continue
        sec_per_cycle = float((t["train_seconds"] / t["cycles"].replace(0, np.nan)).median())
        days = float(t["n_scored"].iloc[0]) / 24
        for lab, x in t.iterrows():
            probe_cycles = float(x["probe_seconds"]) / sec_per_cycle if sec_per_cycle == sec_per_cycle and sec_per_cycle > 0 else 0.0
            eff = float(x["cycles"]) + probe_cycles
            rows.append({"scenario": sc, "seed": None if seed == -1 else int(seed), "group": x["group"], "label": lab,
                         "rel_mae": float(x["mae"]) / float(t.loc["periodic-28", "mae"]), "effective_cycles": eff,
                         "cycles_per_day": eff / days, "days": days})
    return pd.DataFrame(rows)


def regret_curves(terms: pd.DataFrame, kappas=KAPPAS) -> pd.DataFrame:
    stream = terms["scenario"] + "|" + terms["seed"].fillna(-1).astype(int).astype(str)  # pandas 3 keeps None as missing in astype(str)
    out = []
    for k in kappas:
        j = terms["rel_mae"] + k * terms["cycles_per_day"]
        reg = j - j.groupby(stream).transform("min")
        win = (reg <= 1e-12).groupby(terms["label"]).sum()
        g = reg.groupby(terms["label"]).agg(["mean", "max"]).join(win.rename("wins"))
        out.append(g.assign(kappa=k).reset_index())
    return pd.concat(out, ignore_index=True).rename(columns={"mean": "mean_regret", "max": "max_regret"})


def best_intervals(curves: pd.DataFrame) -> list[tuple[float, float, str]]:
    best = curves.loc[curves.groupby("kappa")["mean_regret"].idxmin(), ["kappa", "label"]].sort_values("kappa")
    spans, start, cur = [], None, None
    ks = best["kappa"].tolist()
    for i, (k, lab) in enumerate(zip(best["kappa"], best["label"])):
        if lab != cur:
            if cur is not None:
                spans.append((start, k, cur))
            start, cur = k, lab
    spans.append((start, ks[-1], cur))
    return spans


def run(out: Path) -> dict:
    res = pd.read_csv(out / "results.csv")
    summary = {}
    curves_all = []
    for key in SETS:
        sel = res[res["group"] == "clean"] if key == "clean" else res[res["scenario"] == key]
        terms = stream_terms(sel)
        curves = regret_curves(terms)
        curves_all.append(curves.assign(set=key))
        summary[key] = {"terms": terms, "curves": curves, "intervals": best_intervals(curves)}
    pd.concat(curves_all).to_csv(out / "costmodel.csv", index=False)
    _markdown(out, summary)
    charts.cost_regret({k: v["curves"] for k, v in summary.items()}, {k: v["intervals"] for k, v in summary.items()}, SETS,
                       out / "fig_cost_regret.png")
    return summary


def _near(curves: pd.DataFrame, k: float) -> pd.DataFrame:
    kk = KAPPAS[np.argmin(np.abs(KAPPAS - k))]
    return curves[np.isclose(curves["kappa"], kk)].set_index("label")


NAMES = {"static": "static", "periodic-14": "periodic 14 d", "periodic-28": "periodic 28 d", "periodic-56": "periodic 56 d", "periodic-91": "periodic 91 d",
         "adaptive": "ADWIN", "adaptive-ph": "Page-Hinkley", "adaptive-kswin": "KSWIN", "adaptive-bias": "ADWIN+bias", "probe": "probe"}


def _markdown(out: Path, summary: dict) -> None:
    L = ["# Cost model: cheapest policy for a given price of retraining", "",
         "Reporting only (re-weights the executed results; nothing is tuned). J = MAE / MAE(periodic-28) + kappa x effective cycles per day;",
         "kappa = price of one full retraining cycle in days of the 28-day schedule's average forecast error. Probes are counted at",
         "their measured compute share of a cycle. Regret = J - best J on the same stream, in % of periodic-28's MAE.", ""]
    for key, label in SETS.items():
        s = summary[key]
        L += [f"## {label}", "", "Cheapest policy on average, by kappa:", ""]
        iv = s["intervals"]
        for n, (a, b, lab) in enumerate(iv):
            span = f">= {a:.3g}" if n == len(iv) - 1 else f"{a:.3g} .. {b:.3g}"
            L.append(f"- kappa {span} days: **{NAMES[lab]}**")
        L += ["", "Mean regret (% of periodic-28 MAE; wins = streams where the policy is cheapest):", "",
              "| policy | " + " | ".join(f"kappa {k}" for k in TABLE_KAPPAS) + " |", "|---|" + "---|" * len(TABLE_KAPPAS)]
        for lab in POLICIES:
            cells = []
            for k in TABLE_KAPPAS:
                r = _near(s["curves"], k).loc[lab]
                cells.append(f"{100 * r['mean_regret']:.1f} ({int(r['wins'])})")
            L.append(f"| {NAMES[lab]} | " + " | ".join(cells) + " |")
        L.append("")
    (out / "costmodel.md").write_text("\n".join(L), encoding="utf-8")
