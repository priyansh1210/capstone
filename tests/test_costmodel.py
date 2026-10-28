"""Cost model: regret arithmetic and the price intervals where each policy is cheapest."""

import numpy as np
import pandas as pd

from amm.experiments import costmodel


def _res(rows):
    base = {"scenario": "s", "seed": None, "group": "clean", "n_scored": 100 * 24, "probe_seconds": 0.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_break_even_between_frequent_and_rare_retraining():
    # 100 days; frequent: 2 % lower error with 20 cycles; rare: 2 cycles (5 s per cycle everywhere)
    res = _res([{"label": "periodic-28", "mae": 100.0, "cycles": 10, "train_seconds": 50.0},
                {"label": "periodic-14", "mae": 98.0, "cycles": 20, "train_seconds": 100.0},
                {"label": "periodic-91", "mae": 104.0, "cycles": 2, "train_seconds": 10.0},
                {"label": "probe", "mae": 100.0, "cycles": 4, "train_seconds": 20.0, "probe_seconds": 5.0}])  # probes = 1 cycle
    terms = costmodel.stream_terms(res).set_index("label")
    assert np.isclose(terms.loc["probe", "effective_cycles"], 5.0)
    assert np.isclose(terms.loc["periodic-14", "rel_mae"], 0.98)
    curves = costmodel.regret_curves(terms.reset_index(), [0.0, 0.1, 0.5, 2.0])
    best = curves.loc[curves.groupby("kappa")["mean_regret"].idxmin()].set_index("kappa")["label"]
    # J = rel + kappa * cycles / 100: probe beats periodic-14 above kappa = 0.02 / 0.15 ~ 0.133,
    # periodic-91 beats probe above kappa = 0.04 / 0.03 ~ 1.33
    assert best[0.0] == "periodic-14" and best[0.1] == "periodic-14" and best[0.5] == "probe" and best[2.0] == "periodic-91"
    r = curves[np.isclose(curves["kappa"], 0.5)].set_index("label")["mean_regret"]
    assert np.isclose(r["periodic-14"], (0.98 + 0.5 * 0.2) - (1.0 + 0.5 * 0.05))
    spans = costmodel.best_intervals(curves)
    assert [s[2] for s in spans] == ["periodic-14", "probe", "periodic-91"]
