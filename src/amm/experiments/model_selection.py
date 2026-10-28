"""Choose the initial model on chronological train -> calibration data only.

Fits each candidate family on several trailing windows of the *training*
partition and scores it on the *calibration* partition. The replay partition
is never touched. Also reports how strongly each error scale varies by month
on calibration data, which is how the detector's error signal was chosen.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from amm import paths
from amm.config import load_config
from amm.data.dataset import load_hourly, split_partitions
from amm.data.features import FEATURES, TARGET
from amm.data.quality import outage_mask
from amm.metrics import scaled_error, summarize
from amm.models.candidates import make_model


def run(config_path: str | None = None, models=("ridge", "rf", "hgb"), windows_days=(365, 730, None)) -> dict:
    cfg = load_config(config_path)
    df = load_hourly()
    parts = split_partitions(df, cfg["data"]["partitions"])
    train, cal = parts["train"], parts["calibration"]
    n_before = len(train)
    train = train[~outage_mask(train[TARGET].to_numpy())]
    print(f"[select] excluded {n_before - len(train)} suspected-outage training hours")
    results = []
    best = None
    for w in windows_days:
        tr = train if w is None else train[train["ts_local"] > train["ts_local"].max() - pd.Timedelta(days=w)]
        for name in models:
            m = make_model(name, seed=cfg["seed"])
            t0 = time.perf_counter()
            m.fit(tr[FEATURES], tr[TARGET])
            secs = time.perf_counter() - t0
            pred = m.predict(cal[FEATURES])
            s = summarize(cal[TARGET], pred)
            y = cal[TARGET].to_numpy(float)
            monthly = pd.DataFrame(
                {
                    "m": cal["ts_local"].dt.month.to_numpy(),
                    "abs": np.abs(y - pred),
                    "scaled": scaled_error(y, pred),
                    "pearson": np.abs(y - pred) / np.sqrt(pred + 1.0),
                }
            ).groupby("m").mean()
            cv = (monthly.std() / monthly.mean()).round(3).to_dict()
            row = {
                "model": name,
                "window_days": w,
                "train_rows": int(len(tr)),
                "train_range": [str(tr["ts_local"].min()), str(tr["ts_local"].max())],
                "fit_seconds": round(secs, 2),
                **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()},
                "monthly_cv": cv,
            }
            results.append(row)
            print(
                f"[select] {name:5s} window={str(w):>4s} rows={len(tr):6d} MAE={s['mae']:.1f} "
                f"RMSE={s['rmse']:.1f} scaled={s['scaled']:.3f} bias={s['bias']:+.3f} fit={secs:.1f}s cv={cv}"
            )
            if best is None or s["mae"] < best["mae"]:
                best = row
    out = {
        "partition_train": [str(train["ts_local"].min()), str(train["ts_local"].max())],
        "partition_calibration": [str(cal["ts_local"].min()), str(cal["ts_local"].max())],
        "criterion": "lowest calibration MAE",
        "selected": {"model": best["model"], "window_days": best["window_days"]},
        "results": results,
    }
    paths.REPORTS.mkdir(parents=True, exist_ok=True)
    (paths.REPORTS / "model_selection.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    run()
