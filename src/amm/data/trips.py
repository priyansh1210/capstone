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

A trip is counted in the local wall-clock hour in which it *started*. Every
published row is kept (operators already remove staff/test trips and trips
under 60 s). Raw zips are read in place and never modified.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

START_COLS = ("started_at", "start date", "starttime", "start_time", "start time", "01 - rental details local start time")
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


def aggregate_zip(path: Path, chunksize: int = 750_000) -> tuple[pd.DataFrame, dict]:
    """Return hourly counts for one archive plus parse statistics."""
    parts = []
    stats = {"file": Path(path).name, "rows": 0, "unparsed_rows": 0, "csv_members": [], "skipped_members": [], "schema": None}
    with zipfile.ZipFile(path) as zf:
        for member, opener in _iter_csvs(zf):
            with opener() as fh:
                header = pd.read_csv(fh, nrows=0, encoding_errors="replace").columns.tolist()
            start_col = _pick(header, START_COLS)
            if start_col is None:
                stats["skipped_members"].append(member)  # e.g. station lists
                continue
            stats["csv_members"].append(member)
            member_col = _pick(header, MEMBER_COLS)
            ride_col = _pick(header, (RIDEABLE_COL,))
            use = [c for c in (start_col, member_col, ride_col) if c]
            stats["schema"] = _norm(start_col)
            with opener() as fh:
                reader = pd.read_csv(fh, usecols=use, dtype="str", chunksize=chunksize, encoding_errors="replace")
                for chunk in reader:
                    keys = _hour_keys(chunk[start_col])
                    ok = keys.notna() & keys.str.match(HOUR_RE.pattern)
                    stats["rows"] += len(chunk)
                    stats["unparsed_rows"] += int((~ok).sum())
                    df = pd.DataFrame({"hour": keys[ok]})
                    mt = chunk.loc[ok, member_col].fillna("unknown").str.strip().str.lower() if member_col else pd.Series("unknown", index=df.index)
                    df["member"] = mt.isin(MEMBER_VALUES).astype("int32")
                    df["casual"] = mt.isin(CASUAL_VALUES).astype("int32")
                    df["electric"] = (chunk.loc[ok, ride_col].str.strip() == "electric_bike").astype("int32") if ride_col else 0
                    df["cnt"] = 1
                    parts.append(df.groupby("hour", sort=False)[["cnt", "member", "casual", "electric"]].sum())
    if not parts:
        raise ValueError(f"{Path(path).name}: no trip CSV members (skipped: {stats['skipped_members']})")
    out = pd.concat(parts).groupby(level=0).sum()
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
        print(f"[trips] {Path(z).name}: {st['rows']:,} rows ({st['schema']}), unparsed={st['unparsed_rows']}{skipped}", flush=True)
        frames.append(df)
        all_stats.append(st)
    hourly = pd.concat(frames).groupby(level=0).sum().sort_index()
    hourly.index = pd.to_datetime(hourly.index, format="%Y-%m-%d %H")
    hourly.index.name = "ts_local"
    return hourly, all_stats
