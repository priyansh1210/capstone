"""Generated development data, used ONLY when the raw sources cannot be obtained.

The table has the same schema and calendar as the real hourly table so the
pipeline can be developed and demonstrated, but it is fully synthetic and is
labelled ``GENERATED_FALLBACK`` in dataset_report.json; scenario builders then
mark every scenario as *generated*, and the dashboard shows a warning banner.
It is never presented as Capital Bikeshare or UCI data.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from amm import paths
from amm.data import synthetic
from amm.data.calendar import calendar_features

FALLBACK_KIND = "GENERATED_FALLBACK"


def write_generated_fallback(first_year: int = 2011, last_year: int = 2024, seed: int = 2024) -> pd.DataFrame:
    days = (pd.Timestamp(f"{last_year}-12-31") - pd.Timestamp(f"{first_year}-01-01")).days + 1
    df = synthetic.generate(seed, days, start=f"{first_year}-01-01")
    ts = pd.DatetimeIndex(df["ts_local"])
    cal = calendar_features(ts, base_year=first_year)
    for c in cal.columns:
        df[c] = cal[c].to_numpy()
    # a visible level trend and a 2020 shock, so drift handling can be exercised
    years = ts.year.to_numpy() - first_year
    level = 1.0 + 0.06 * years
    level = np.where((ts >= "2020-03-15") & (ts < "2020-09-01"), level * 0.5, level)
    df["cnt"] = np.round(df["cnt"].to_numpy() * level).astype("int64")
    df["member"], df["casual"], df["electric"] = 0, 0, 0
    df["dewpoint_c"] = np.nan
    paths.PROCESSED.mkdir(parents=True, exist_ok=True)
    df.drop(columns=["seq"]).to_parquet(paths.PROCESSED / "hourly.parquet", index=False)
    (paths.PROCESSED / "dataset_report.json").write_text(
        json.dumps({"data_kind": FALLBACK_KIND, "rows": len(df), "seed": seed,
                    "warning": "GENERATED development data - NOT Capital Bikeshare/UCI observations"}, indent=2)
    )
    return df


def is_fallback() -> bool:
    p = paths.PROCESSED / "dataset_report.json"
    if not p.exists():
        return False
    return json.loads(p.read_text()).get("data_kind") == FALLBACK_KIND
