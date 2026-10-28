"""Load the processed hourly table and split it chronologically."""

from __future__ import annotations

import pandas as pd

from amm import paths


def load_hourly(path=None) -> pd.DataFrame:
    p = path or paths.PROCESSED / "hourly.parquet"
    if not p.exists():
        raise FileNotFoundError(f"{p} not found - run `python -m amm prepare-data` first")
    df = pd.read_parquet(p)
    df["ts_local"] = pd.to_datetime(df["ts_local"])
    return df.sort_values("instant").reset_index(drop=True)


def split_partitions(df: pd.DataFrame, partitions: dict) -> dict[str, pd.DataFrame]:
    """Chronological, non-overlapping partitions given as inclusive date ranges.

    Raises if the ranges overlap or are out of order, so a misconfiguration can
    never produce a random or leaky split.
    """
    out = {}
    prev_end = None
    for name in ("train", "calibration", "replay"):
        start_s, end_s = partitions[name]
        if end_s == "auto":
            # last full day on which weather was observed (inputs must exist; e.g. DC 2025)
            last = df.loc[df["temp_c"].notna(), "ts_local"].max()
            end_s = str((last.normalize() - pd.Timedelta(days=1)).date())
        start, end = pd.Timestamp(start_s), pd.Timestamp(end_s)
        end = end + pd.Timedelta(hours=23) if end == end.normalize() else end
        if prev_end is not None and start <= prev_end:
            raise ValueError(f"partition {name} starts {start} before previous ends {prev_end}")
        mask = (df["ts_local"] >= start) & (df["ts_local"] <= end)
        out[name] = df.loc[mask].copy()
        prev_end = end
    return out
