"""Paired comparison statistics and the Pareto/rolling chart renderers."""

import numpy as np
import pandas as pd

from amm.experiments import charts, stats


def _ar1(n, phi, sd, seed):
    rng = np.random.default_rng(seed)
    e = rng.normal(0, sd, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def test_block_bootstrap_covers_true_difference_and_dm_separates():
    noise = _ar1(700, 0.7, 5.0, 1)
    lo, hi = stats.block_bootstrap_ci(-3.0 + noise)
    assert lo < -3.0 < hi and hi < 0  # a real 3-trip/h improvement is resolved
    stat, p = stats.diebold_mariano(-3.0 + noise)
    assert stat < 0 and p < 0.05
    _, p0 = stats.diebold_mariano(_ar1(700, 0.7, 5.0, 2))
    assert p0 > 0.01  # pure noise is usually not significant


def test_paired_uses_common_days():
    days = pd.date_range("2020-01-01", periods=60, freq="D")
    a = pd.DataFrame({"day": days, "mae": 10.0})
    b = pd.DataFrame({"day": days[5:], "mae": 12.0})
    r = stats.paired(a, b)
    assert r["n_days"] == 55 and abs(r["diff"] + 2.0) < 1e-9 and abs(r["rel_diff"] + 2 / 12) < 1e-9


def test_charts_render(tmp_path):
    rows = []
    for lab, mae, comp in [("static", 130, 0), ("periodic-14", 80, 700), ("periodic-28", 82, 360), ("periodic-56", 90, 180),
                           ("periodic-91", 95, 120), ("adaptive", 115, 70), ("adaptive-ph", 110, 90), ("adaptive-kswin", 120, 40),
                           ("adaptive-bias", 85, 220), ("probe", 83, 150), ("oracle", 100, 30), ("probe-no-test", 84, 300)]:
        rows.append({"scenario": "city_x_unmodified", "label": lab, "mae": mae, "compute_seconds": comp, "cycles": 1})
    charts.pareto(pd.DataFrame(rows), ["city_x_unmodified"], tmp_path / "p.png", "test")
    days = pd.date_range("2020-01-01", periods=200, freq="D")
    d = {lab: pd.DataFrame({"day": days, "mae": np.linspace(50, 80, 200)}) for lab in ("static", "periodic-28", "adaptive", "probe")}
    charts.rolling_multi(d, "test", tmp_path / "r.png", {"start": "2020-03-01", "end": None})
    assert (tmp_path / "p.png").stat().st_size > 10_000 and (tmp_path / "r.png").stat().st_size > 10_000
