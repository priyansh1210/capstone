"""Paired comparison of two policies on the same replay days.

Daily MAE series are autocorrelated (weather spells, seasons, regime changes), so
naive i.i.d. tests are over-confident. We report:

* a moving-block bootstrap 95 % CI of the mean daily MAE difference (blocks of
  28 days, 2,000 resamples, fixed seed), and
* the Diebold-Mariano statistic for equal predictive accuracy with a Newey-West
  (Bartlett) long-run variance, lag 7, two-sided normal p-value.

A negative difference means policy A has the lower error.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def block_bootstrap_ci(diff, block: int = 28, reps: int = 2000, seed: int = 0, level: float = 0.95) -> tuple[float, float]:
    d = np.asarray(diff, float)
    n = len(d)
    if n < 2 * block:
        block = max(1, n // 4)
    rng = np.random.default_rng(seed)
    nb = math.ceil(n / block)
    means = np.empty(reps)
    for i in range(reps):
        starts = rng.integers(0, n - block + 1, nb)
        sample = np.concatenate([d[s : s + block] for s in starts])[:n]
        means[i] = sample.mean()
    lo, hi = np.quantile(means, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def diebold_mariano(diff, lag: int = 7) -> tuple[float, float]:
    d = np.asarray(diff, float)
    n = len(d)
    if n < 10 or d.std() == 0:
        return float("nan"), float("nan")
    e = d - d.mean()
    var = float(e @ e) / n
    for k in range(1, lag + 1):
        var += 2 * (1 - k / (lag + 1)) * float(e[k:] @ e[:-k]) / n
    if var <= 0:
        return float("nan"), float("nan")
    stat = d.mean() / math.sqrt(var / n)
    p = math.erfc(abs(stat) / math.sqrt(2))  # two-sided normal
    return float(stat), float(p)


def paired(daily_a: pd.DataFrame, daily_b: pd.DataFrame) -> dict:
    """Compare two runs' daily series (columns: day, mae, n) on their common days,
    weighting each day equally."""
    a = daily_a.set_index("day")["mae"]
    b = daily_b.set_index("day")["mae"]
    common = a.index.intersection(b.index)
    diff = (a.loc[common] - b.loc[common]).to_numpy()
    lo, hi = block_bootstrap_ci(diff)
    dm, p = diebold_mariano(diff)
    base = float(b.loc[common].mean())
    return {
        "n_days": int(len(common)),
        "mae_a": float(a.loc[common].mean()),
        "mae_b": base,
        "diff": float(diff.mean()),
        "rel_diff": float(diff.mean() / base) if base else float("nan"),
        "ci_lo": lo,
        "ci_hi": hi,
        "dm_stat": dm,
        "dm_p": p,
    }
