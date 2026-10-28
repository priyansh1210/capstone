"""Parse NOAA ISD-Lite hourly observations (UTC) for DCA.

ISD-Lite fields (whitespace separated, -9999 = missing):
year month day hour(UTC) air_temp(C*10) dew_point(C*10) slp(hPa*10)
wind_dir(deg) wind_speed(m/s*10) sky_cover_code precip_1h(mm*10) precip_6h(mm*10)
A 1-hour precipitation of -1 means "trace" and is stored as 0.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd

ISD_COLS = ["year", "month", "day", "hour", "temp", "dewp", "slp", "wdir", "wspd", "sky", "p1h", "p6h"]

# Approximate cloud fraction for ISD sky-condition total coverage codes 0-19.
SKY_FRACTION = {
    0: 0.0, 1: 1 / 8, 2: 2 / 8, 3: 3 / 8, 4: 4 / 8, 5: 5 / 8, 6: 6 / 8, 7: 7 / 8, 8: 1.0,
    9: 1.0, 10: 0.5, 11: 0.25, 12: 0.4, 13: 0.45, 14: 0.6, 15: 0.7, 16: 0.75, 17: 0.9, 18: 1.0, 19: 1.0,
}


def parse_isd_lite(path: Path) -> pd.DataFrame:
    with gzip.open(path, "rt") as fh:
        df = pd.read_csv(fh, sep=r"\s+", header=None, names=ISD_COLS, dtype="int64")
    df = df.replace(-9999, np.nan)
    ts = pd.to_datetime(df[["year", "month", "day", "hour"]].astype("int64"))
    out = pd.DataFrame(index=pd.DatetimeIndex(ts.dt.tz_localize("UTC"), name="ts_utc"))
    out["temp_c"] = df["temp"].to_numpy() / 10.0
    out["dewpoint_c"] = df["dewp"].to_numpy() / 10.0
    out["pressure_hpa"] = df["slp"].to_numpy() / 10.0
    out["windspeed_ms"] = df["wspd"].to_numpy() / 10.0
    out["cloud_cover"] = df["sky"].map(SKY_FRACTION).to_numpy()
    p1 = df["p1h"].to_numpy(dtype=float)
    out["precip_1h_mm"] = np.where(p1 == -1, 0.0, p1 / 10.0)
    return out


def derive(w: pd.DataFrame) -> pd.DataFrame:
    """Add relative humidity, apparent temperature and a weathersit-like class."""
    t, td = w["temp_c"], w["dewpoint_c"]
    # Magnus formula (Alduchov & Eskridge 1996 coefficients)
    rh = 100 * np.exp(17.625 * td / (243.04 + td)) / np.exp(17.625 * t / (243.04 + t))
    w = w.copy()
    w["humidity"] = rh.clip(0, 100)
    # Steadman apparent temperature (Australian BoM, no radiation term)
    e = w["humidity"] / 100 * 6.105 * np.exp(17.27 * t / (237.7 + t))
    w["atemp_c"] = t + 0.33 * e - 0.70 * w["windspeed_ms"] - 4.0
    p = w["precip_1h_mm"]
    sit = np.where(w["cloud_cover"] > 0.5, 2, 1)
    sit = np.where(p > 0, 3, sit)
    sit = np.where(p >= 2.5, 4, sit)
    w["weathersit"] = np.where(w["cloud_cover"].isna() & p.isna(), np.nan, sit)
    return w


def load_weather(files: list[Path]) -> pd.DataFrame:
    frames = [parse_isd_lite(f) for f in sorted(files)]
    w = pd.concat(frames)
    w = w[~w.index.duplicated(keep="first")].sort_index()
    return derive(w)


CONTINUOUS = ["temp_c", "dewpoint_c", "pressure_hpa", "windspeed_ms", "cloud_cover", "humidity", "atemp_c"]


def lagged_weather_for_local_hours(
    w: pd.DataFrame, local_hours: pd.DatetimeIndex, tz: str, lag_hours: int = 1, max_ffill_hours: int = 3
) -> tuple[pd.DataFrame, dict]:
    """Weather features for each local target hour using only observations
    reported at least ``lag_hours`` before the start of that hour.

    The UTC series is put on a complete hourly grid; continuous fields may be
    carried forward from *earlier* observations for up to ``max_ffill_hours``
    (never backward). Precipitation is never carried forward.
    """
    grid = pd.date_range(w.index.min().floor("h"), w.index.max().ceil("h"), freq="h", tz="UTC")
    g = w.reindex(grid)
    missing_obs = g["temp_c"].isna()
    g[CONTINUOUS] = g[CONTINUOUS].ffill(limit=max_ffill_hours)
    g["weathersit"] = g["weathersit"].ffill(limit=max_ffill_hours)
    # Value usable for target hour H is the observation at H - lag.
    g = g.shift(lag_hours, freq="h")

    # Map local wall-clock target hours to UTC. Ambiguous fall-back hours map to
    # the first (DST) occurrence; nonexistent spring-forward hours are absent
    # from the demand grid already.
    utc = local_hours.tz_localize(tz, ambiguous=np.ones(len(local_hours), dtype=bool), nonexistent="NaT").tz_convert("UTC")
    feats = g.reindex(utc)
    feats.index = local_hours
    stats = {
        "isd_records": int(len(w)),
        "isd_first_utc": str(w.index.min()),
        "isd_last_utc": str(w.index.max()),
        "utc_grid_hours": int(len(grid)),
        "utc_hours_without_observation": int(missing_obs.sum()),
        "target_hours_missing_temp_after_ffill": int(feats["temp_c"].isna().sum()),
        "target_hours_missing_precip": int(feats["precip_1h_mm"].isna().sum()),
        "lag_hours": lag_hours,
        "max_ffill_hours": max_ffill_hours,
    }
    return feats, stats
