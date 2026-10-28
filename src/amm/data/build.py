"""Assemble the hourly modelling table and its validation report.

Output: ``data/processed/hourly.parquet`` (one row per local wall-clock hour)
and ``data/processed/dataset_report.json``. Raw files are only read.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from amm import paths
from amm.data import trips as trips_mod
from amm.data import weather as weather_mod
from amm.data.calendar import calendar_features
from amm.data.features import FEATURES, TARGET

TZ = "America/New_York"
OUTAGE_RUN_HOURS = 6


def local_wall_clock_grid(first_year: int, last_year: int) -> pd.DatetimeIndex:
    """Every local wall-clock hour that exists: spring-forward hours are absent,
    fall-back hours appear once (both physical hours share one wall-clock label)."""
    aware = pd.date_range(f"{first_year}-01-01 00:00", f"{last_year}-12-31 23:00", freq="h", tz=TZ)
    naive = aware.tz_localize(None)
    return pd.DatetimeIndex(naive.unique(), name="ts_local")


def _zero_runs(cnt: pd.Series, min_run: int) -> pd.Series:
    z = cnt.eq(0).to_numpy()
    flag = np.zeros(len(z), dtype=bool)
    i = 0
    while i < len(z):
        if z[i]:
            j = i
            while j < len(z) and z[j]:
                j += 1
            if j - i >= min_run:
                flag[i:j] = True
            i = j
        else:
            i += 1
    return pd.Series(flag, index=cnt.index)


def uci_crosscheck(hourly: pd.DataFrame) -> dict:
    zpath = paths.RAW_UCI / "bike_sharing_dataset.zip"
    if not zpath.exists():
        return {"available": False}
    with zipfile.ZipFile(zpath) as zf:
        uci = pd.read_csv(io.BytesIO(zf.read("hour.csv")))
    uci["ts_local"] = pd.to_datetime(uci["dteday"]) + pd.to_timedelta(uci["hr"], unit="h")
    m = uci.set_index("ts_local")[["cnt"]].join(hourly[["cnt"]], rsuffix="_ours", how="inner")
    diff = m["cnt_ours"] - m["cnt"]
    return {
        "available": True,
        "uci_rows": int(len(uci)),
        "matched_hours": int(len(m)),
        "exact_match_share": round(float((diff == 0).mean()), 4),
        "within_2_share": round(float((diff.abs() <= 2).mean()), 4),
        "mean_abs_diff": round(float(diff.abs().mean()), 3),
        "uci_total": int(m["cnt"].sum()),
        "ours_total": int(m["cnt_ours"].sum()),
        "relative_total_diff": round(float(m["cnt_ours"].sum() / m["cnt"].sum() - 1), 5),
        "note": "UCI hour.csv (Fanaee-T 2013) was derived from the same Capital Bikeshare archive for 2011-2012.",
    }


def build(first_year: int = 2011, last_year: int = 2024) -> tuple[pd.DataFrame, dict]:
    paths.ensure_dirs()
    sources = json.loads((paths.RAW / "SOURCES.json").read_text()) if (paths.RAW / "SOURCES.json").exists() else {}
    zips = [paths.RAW_TRIPS / n for n in trips_mod_names(first_year, last_year)]
    missing = [z.name for z in zips if not z.exists()]
    if missing:
        raise FileNotFoundError(f"missing trip archives: {missing[:5]}... run `amm prepare-data` first")

    counts, parse_stats = trips_mod.aggregate_all(zips)
    grid = local_wall_clock_grid(first_year, last_year)
    outside = counts.index.difference(grid)
    trips_outside = int(counts.loc[outside, "cnt"].sum()) if len(outside) else 0
    df = counts.reindex(grid).fillna(0).astype("int64")
    df["suspected_outage"] = _zero_runs(df["cnt"], OUTAGE_RUN_HOURS).astype(int)

    wfiles = sorted(paths.RAW_WEATHER.glob("724050-13743-*.gz"))
    w = weather_mod.load_weather(wfiles)
    wx, wstats = weather_mod.lagged_weather_for_local_hours(w, grid, TZ)
    cal = calendar_features(grid, base_year=first_year)
    df = df.join(cal).join(wx[[c for c in FEATURES if c in wx.columns] + ["dewpoint_c"]])
    df.insert(0, "instant", np.arange(len(df)))
    df = df.reset_index()

    report = describe(df, first_year, last_year)
    report.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data_kind": "source_observations_aggregated",
            "trip_rows_read": int(sum(s["rows"] for s in parse_stats)),
            "trip_rows_unparsed": int(sum(s["unparsed_rows"] for s in parse_stats)),
            "trips_in_nonexistent_local_hours_dropped": trips_outside,
            "nonexistent_local_hours_with_trips": [str(t) for t in outside[:20]],
            "weather": wstats,
            "uci_crosscheck": uci_crosscheck(df.set_index("ts_local")),
            "source_files": [
                {k: f[k] for k in ("kind", "name", "size", "sha256", "origin")} for f in sources.get("files", [])
            ],
        }
    )
    # atomic replace: concurrent readers never see a partially written file
    tmp = paths.PROCESSED / "hourly.parquet.tmp"
    df.to_parquet(tmp, index=False)
    tmp.replace(paths.PROCESSED / "hourly.parquet")
    (paths.PROCESSED / "dataset_report.json").write_text(json.dumps(report, indent=2, default=str))
    return df, report


def trips_mod_names(first_year: int, last_year: int) -> list[str]:
    from amm.data.download import trip_file_names

    return trip_file_names(first_year, last_year)


def describe(df: pd.DataFrame, first_year: int, last_year: int) -> dict:
    ts = df["ts_local"]
    full_aware = pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31 23:00", freq="h", tz=TZ)
    yearly = df.groupby(ts.dt.year)["cnt"].agg(["sum", "mean", "max"]).round(1)
    monthly = df.groupby(ts.dt.to_period("M"))["cnt"].sum()
    outages = df.loc[df["suspected_outage"] == 1, "ts_local"]
    outage_days = sorted({str(d.date()) for d in outages})
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "date_range_local": [str(ts.min()), str(ts.max())],
        "physical_hours_in_range": int(len(full_aware)),
        "dst_spring_forward_hours_absent": int(len(full_aware) - len(full_aware.tz_localize(None).unique()) + 0),
        "zero_trip_hours": int((df["cnt"] == 0).sum()),
        "suspected_outage_hours": int(df["suspected_outage"].sum()),
        "suspected_outage_days": outage_days,
        "missingness": {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()},
        "target_summary": {k: round(float(v), 2) for k, v in df[TARGET].describe().items()},
        "yearly_cnt": {str(k): v for k, v in yearly.to_dict(orient="index").items()},
        "months_with_zero_trips": [str(p) for p, v in monthly.items() if v == 0],
        "monthly_cnt": {str(p): int(v) for p, v in monthly.items()},
    }


def build_city(key: str, workers: int = 1) -> tuple[pd.DataFrame, dict]:
    """Hourly table for one city from data/raw/<city>/ -> data/processed/<city>/hourly.parquet."""
    from amm.data.cities import CITIES

    c = CITIES[key]
    raw = paths.RAW / key
    zips = sorted((raw / "trips").glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"no trip archives in {raw / 'trips'} - run `amm download-city --city {key}`")
    counts, parse_stats = trips_mod.aggregate_all(zips, workers=workers)
    counts = counts[(counts.index.year >= c.first_year) & (counts.index.year <= c.last_year)]
    aware = pd.date_range(f"{c.first_year}-01-01 00:00", f"{c.last_year}-12-31 23:00", freq="h", tz=c.tz)
    grid = pd.DatetimeIndex(aware.tz_localize(None).unique(), name="ts_local")
    outside = counts.index.difference(grid)
    df = counts.reindex(grid).fillna(0).astype("int64")

    # Archive gaps: whole months without a single trip between the first and last
    # trip are missing data (e.g. Bay Wheels has no file for 2020-04), not zero demand.
    first, last = counts.index.min(), counts.index.max()
    monthly = df["cnt"].groupby(df.index.to_period("M")).sum()
    gap_months = [p for p, v in monthly.items() if v == 0 and first.to_period("M") <= p <= last.to_period("M")]
    in_range = (df.index >= first.floor("D")) & (df.index <= last.floor("D") + pd.Timedelta(hours=23))
    gap = df.index.to_period("M").isin(gap_months) | ~in_range
    df["suspected_outage"] = _zero_runs(df["cnt"], OUTAGE_RUN_HOURS).astype(int)

    wfiles = sorted((raw / "weather").glob(f"{c.station}-*.gz"))
    w = weather_mod.load_weather(wfiles)
    wx, wstats = weather_mod.lagged_weather_for_local_hours(w, grid, c.tz)
    cal = calendar_features(grid, base_year=c.first_year, holidays=c.holidays)
    df = df.join(cal).join(wx[[f for f in FEATURES if f in wx.columns] + ["dewpoint_c"]])
    df.insert(0, "instant", np.arange(len(df)))
    dropped = int(gap.sum())
    df = df[~gap].reset_index()

    rep = describe(df, c.first_year, c.last_year)
    yr = df["ts_local"].dt.year
    wd = df["workingday"] == 1
    prof = df[wd].groupby([yr[wd], df.loc[wd, "hr"]])["cnt"].sum().unstack()
    rep.update({
        "city": key, "label": c.label, "tz": c.tz, "station": f"{c.station} {c.station_name}",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_kind": "source_observations_aggregated",
        "trip_rows_read": int(sum(s["rows"] for s in parse_stats)),
        "trip_rows_unparsed": int(sum(s["unparsed_rows"] for s in parse_stats)),
        "skipped_non_trip_csvs": sorted({m for s in parse_stats for m in s["skipped_members"]}),
        "trips_in_nonexistent_local_hours_dropped": int(counts.loc[outside, "cnt"].sum()) if len(outside) else 0,
        "archive_gap_months": [str(p) for p in gap_months],
        "hours_dropped_as_archive_gaps_or_outside_service": dropped,
        "first_trip": str(first), "last_trip": str(last),
        "last_hour_with_observed_temperature": str(df.loc[df["temp_c"].notna(), "ts_local"].max()),
        # local-time sanity check: working-day peak hours per year (expected ~8 and ~17)
        "workingday_peak_hours": {str(y): [int(r.loc[5:11].idxmax()), int(r.loc[14:20].idxmax())] for y, r in prof.iterrows()},
        "weather": wstats,
    })
    out = paths.PROCESSED / key
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "hourly.parquet.tmp"
    df.to_parquet(tmp, index=False)
    tmp.replace(out / "hourly.parquet")
    (out / "dataset_report.json").write_text(json.dumps(rep, indent=2, default=str))
    return df, rep
