"""Aggregate raw bike-share trip records to hourly system demand.

Works for every archive used here (Capital Bikeshare, Divvy, Bay Wheels, Citi Bike):

* start-time column found case-insensitively among the known names
  (``started_at``, ``Start date``, ``starttime``, ``start_time``, ``Start Time``,
  ``01 - Rental Details Local Start Time``); CSVs without one (station lists) are skipped
* timestamps: ISO prefix ``YYYY-MM-DD HH`` fast path; otherwise the format is
  detected per chunk among US-style variants (``4/30/2016 23:59``,
  ``12/1/2014 00:00:28``), with a mixed-format fallback for the remainder
* member/casual from ``member_casual`` / ``Member type`` / ``usertype`` / ``User Type``
  (Member/Subscriber vs Casual/Customer), kept for analysis only
* archives may contain folders and nested zips (Citi Bike yearly archives)
* the same trips may appear in several members of one archive: the Citi Bike 2018
  archive holds every month as a whole-month CSV *and* as 1M-row parts in month
  folders (differently quoted), plus an extra copy of April's parts. A trip seen
  in an earlier member is dropped from later members, matched on the ride id or on
  (start time, end time, bike id); repeats *within* one member are kept as published

A trip is counted in the local wall-clock hour in which it *started*. Every
published row is kept (operators already remove staff/test trips and trips
under 60 s). Raw zips are read in place and never modified.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

START_COLS = ("started_at", "start date", "starttime", "start_time", "start time", "01 - rental details local start time")
ID_COLS = ("ride_id", "rental_id", "trip_id", "trip id", "01 - rental details rental id")
END_COLS = ("ended_at", "end date", "stoptime", "end_time", "end time", "01 - rental details local end time")
BIKE_COLS = ("bikeid", "bike number", "bike_id", "bike id", "01 - rental details bike id")
MEMBER_COLS = ("member_casual", "member type", "usertype", "user_type", "user type")
RIDEABLE_COL = "rideable_type"
HOUR_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}$")
US_FORMATS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S.%f", "%m/%d/%y %H:%M")
MEMBER_VALUES, CASUAL_VALUES = {"member", "subscriber"}, {"casual", "customer"}


def _norm(c: str) -> str:
    return c.strip().strip('"').strip().lower()


def _pick(header: list[str], candidates) -> str | None:
    by_norm = {_norm(h): h for h in header}
    return next((by_norm[c] for c in candidates if c in by_norm), None)


def _hour_keys(start: pd.Series) -> pd.Series:
    """Map raw start timestamps to 'YYYY-MM-DD HH' local-hour keys."""
    s = start.astype("str").str.strip()
    keys = s.str.slice(0, 13)
    bad = ~keys.str.match(HOUR_RE.pattern)
    if not bad.any():
        return keys
    sub = s[bad]
    parsed = pd.Series(pd.NaT, index=sub.index, dtype="datetime64[ns]")
    for fmt in US_FORMATS:
        todo = parsed.isna()
        if not todo.any():
            break
        parsed[todo] = pd.to_datetime(sub[todo], format=fmt, errors="coerce")
    todo = parsed.isna()
    if todo.any():  # anything still unparsed: slow, general parser
        parsed[todo] = pd.to_datetime(sub[todo], errors="coerce", format="mixed")
    keys = keys.copy()
    keys[bad] = parsed.dt.strftime("%Y-%m-%d %H")
    return keys


def _iter_csvs(zf: zipfile.ZipFile, prefix: str = ""):
    """Yield (name, opener) for every CSV in the archive, descending into nested zips."""
    for n in zf.namelist():
        base = Path(n).name
        if n.startswith("__MACOSX") or n.endswith("/") or base.startswith("."):
            continue
        if n.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(zf.read(n))) as inner:
                yield from _iter_csvs(inner, prefix + n + "/")
        elif n.lower().endswith(".csv"):
            data = zf.read(n) if prefix else None  # nested members must be read before the inner zip closes
            yield prefix + n, (lambda n=n, data=data: io.BytesIO(data) if data is not None else zf.open(n))


def _trip_keys(header: list[str], start_col: str) -> list[str] | None:
    """Columns that identify a trip: the ride id, else (start, end, bike); None if not enough."""
    rid = _pick(header, ID_COLS)
    if rid:
        return [rid]
    end, bike = _pick(header, END_COLS), _pick(header, BIKE_COLS)
    return [start_col, end, bike] if end and bike else None


def _first_member_only(h: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Keep each trip hash only in the first member it occurs in (all its rows there)."""
    order = np.lexsort((m, h))
    hs, ms = h[order], m[order]
    starts = np.r_[True, hs[1:] != hs[:-1]]
    first_m = ms[np.maximum.accumulate(np.where(starts, np.arange(len(hs)), 0))]
    keep = np.empty(len(h), dtype=bool)
    keep[order] = ms == first_m
    return keep


EPOCH = pd.Timestamp("1970-01-01")


def aggregate_zip(path: Path, chunksize: int = 750_000) -> tuple[pd.DataFrame, dict]:
    """Return hourly counts for one archive plus parse statistics."""
    cols = {k: [] for k in ("hour", "member", "casual", "electric", "hash", "idx")}
    stats = {"file": Path(path).name, "rows": 0, "unparsed_rows": 0, "csv_members": [], "skipped_members": [], "schema": None,
             "cross_member_duplicates_removed": 0, "members_without_trip_key": []}
    with zipfile.ZipFile(path) as zf:
        for member, opener in _iter_csvs(zf):
            with opener() as fh:
                header = pd.read_csv(fh, nrows=0, encoding_errors="replace").columns.tolist()
            start_col = _pick(header, START_COLS)
            if start_col is None:
                stats["skipped_members"].append(member)  # e.g. station lists
                continue
            idx = len(stats["csv_members"])
            stats["csv_members"].append(member)
            member_col = _pick(header, MEMBER_COLS)
            ride_col = _pick(header, (RIDEABLE_COL,))
            key_cols = _trip_keys(header, start_col)
            if key_cols is None:
                stats["members_without_trip_key"].append(member)
            use = list(dict.fromkeys(c for c in (start_col, member_col, ride_col, *(key_cols or [])) if c))
            stats["schema"] = _norm(start_col)
            with opener() as fh:
                reader = pd.read_csv(fh, usecols=use, dtype="str", chunksize=chunksize, encoding_errors="replace")
                for chunk in reader:
                    keys = _hour_keys(chunk[start_col])
                    ok = keys.notna() & keys.str.match(HOUR_RE.pattern)
                    ts = pd.to_datetime(keys.where(ok), format="%Y-%m-%d %H", errors="coerce")
                    ok &= ts.notna()
                    stats["rows"] += len(chunk)
                    stats["unparsed_rows"] += int((~ok).sum())
                    c = chunk.loc[ok]
                    cols["hour"].append(((ts[ok] - EPOCH) // pd.Timedelta(hours=1)).to_numpy(dtype="int32"))
                    mt = c[member_col].fillna("unknown").str.strip().str.lower() if member_col else pd.Series("unknown", index=c.index)
                    cols["member"].append(mt.isin(MEMBER_VALUES).to_numpy(dtype="int8"))
                    cols["casual"].append(mt.isin(CASUAL_VALUES).to_numpy(dtype="int8"))
                    cols["electric"].append((c[ride_col].str.strip() == "electric_bike").to_numpy(dtype="int8") if ride_col else np.zeros(len(c), "int8"))
                    if key_cols:  # quoting differs between copies; the CSV parser removes it, whitespace is stripped here
                        h = pd.util.hash_pandas_object(c[key_cols].apply(lambda s: s.str.strip()), index=False).to_numpy()
                    else:  # unique per member: such rows are never treated as duplicates
                        h = np.arange(stats["rows"] - len(chunk), stats["rows"] - len(chunk) + len(c), dtype="uint64") ^ np.uint64(idx << 48)
                    cols["hash"].append(h)
                    cols["idx"].append(np.full(len(c), idx, dtype="int32"))
    if not stats["csv_members"]:
        raise ValueError(f"{Path(path).name}: no trip CSV members (skipped: {stats['skipped_members']})")
    a = {k: np.concatenate(v) if v else np.empty(0) for k, v in cols.items()}
    keep = _first_member_only(a["hash"], a["idx"]) if len(stats["csv_members"]) > 1 else np.ones(len(a["hour"]), dtype=bool)
    stats["cross_member_duplicates_removed"] = int((~keep).sum())
    df = pd.DataFrame({"cnt": np.ones(int(keep.sum()), "int64"), **{k: a[k][keep].astype("int64") for k in ("member", "casual", "electric")}},
                      index=a["hour"][keep])
    out = df.groupby(level=0).sum()
    out.index = (EPOCH + pd.to_timedelta(out.index, unit="h")).strftime("%Y-%m-%d %H")
    return out, stats


def _one(p):
    return aggregate_zip(Path(p))


def aggregate_all(zips: list[Path], workers: int = 1) -> tuple[pd.DataFrame, list[dict]]:
    frames, all_stats = [], []
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_one, [str(z) for z in zips]))
    else:
        results = [aggregate_zip(z) for z in zips]
    for z, (df, st) in zip(zips, results):
        skipped = f", skipped {len(st['skipped_members'])} non-trip CSV(s)" if st["skipped_members"] else ""
        dups = f", {st['cross_member_duplicates_removed']:,} repeated across members removed" if st["cross_member_duplicates_removed"] else ""
        print(f"[trips] {Path(z).name}: {st['rows']:,} rows ({st['schema']}), unparsed={st['unparsed_rows']}{skipped}{dups}", flush=True)
        frames.append(df)
        all_stats.append(st)
    hourly = pd.concat(frames).groupby(level=0).sum().sort_index()
    hourly.index = pd.to_datetime(hourly.index, format="%Y-%m-%d %H")
    hourly.index.name = "ts_local"
    return hourly, all_stats
