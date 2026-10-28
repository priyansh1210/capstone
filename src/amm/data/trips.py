"""Aggregate raw Capital Bikeshare trip records to hourly system demand.

Two schemas exist in the archive:

* legacy (2011 - Mar 2020): ``Start date``, ``Member type`` (Member/Casual/Unknown)
* current (Apr 2020 -):     ``started_at``, ``member_casual``, ``rideable_type``

A trip is counted in the local wall-clock hour in which it *started*
(``YYYY-MM-DD HH`` prefix of the start timestamp, which the operator publishes
in US Eastern local time). We keep every published row: the operator states
that staff/test trips and trips under 60 s were already removed. Raw zips are
read in place and never modified.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

START_COLS = ("Start date", "started_at")
MEMBER_COLS = ("Member type", "member_casual")
RIDEABLE_COL = "rideable_type"
HOUR_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}$")


def _csv_members(zf: zipfile.ZipFile) -> list[str]:
    return [
        n
        for n in zf.namelist()
        if n.lower().endswith(".csv") and not n.startswith("__MACOSX") and not Path(n).name.startswith(".")
    ]


def _hour_keys(start: pd.Series) -> pd.Series:
    """Map raw start timestamps to 'YYYY-MM-DD HH' local-hour keys."""
    keys = start.astype("str").str.slice(0, 13)
    bad = ~keys.str.match(HOUR_RE.pattern)
    if bad.any():
        # Fallback for any non-ISO rows: parse fully, then format.
        parsed = pd.to_datetime(start[bad], errors="coerce", format="mixed")
        keys = keys.copy()
        keys[bad] = parsed.dt.strftime("%Y-%m-%d %H")
    return keys


def aggregate_zip(path: Path, chunksize: int = 750_000) -> tuple[pd.DataFrame, dict]:
    """Return hourly counts for one archive plus parse statistics."""
    parts = []
    stats = {"file": path.name, "rows": 0, "unparsed_rows": 0, "csv_members": [], "schema": None}
    with zipfile.ZipFile(path) as zf:
        for member in _csv_members(zf):
            stats["csv_members"].append(member)
            with zf.open(member) as fh:
                header = pd.read_csv(fh, nrows=0).columns.str.strip().tolist()
            start_col = next((c for c in START_COLS if c in header), None)
            if start_col is None:
                raise ValueError(f"{path.name}/{member}: no start-time column in {header}")
            member_col = next((c for c in MEMBER_COLS if c in header), None)
            use = [c for c in (start_col, member_col, RIDEABLE_COL if RIDEABLE_COL in header else None) if c]
            stats["schema"] = "current" if start_col == "started_at" else "legacy"
            with zf.open(member) as fh:
                reader = pd.read_csv(
                    fh,
                    usecols=lambda c: c.strip() in use,
                    dtype="str",
                    chunksize=chunksize,
                )
                for chunk in reader:
                    chunk.columns = chunk.columns.str.strip()
                    keys = _hour_keys(chunk[start_col])
                    ok = keys.notna() & keys.str.match(HOUR_RE.pattern)
                    stats["rows"] += len(chunk)
                    stats["unparsed_rows"] += int((~ok).sum())
                    df = pd.DataFrame({"hour": keys[ok]})
                    mt = (
                        chunk.loc[ok, member_col].fillna("unknown").str.strip().str.lower()
                        if member_col
                        else pd.Series("unknown", index=df.index)
                    )
                    df["member"] = (mt == "member").astype("int32")
                    df["casual"] = (mt == "casual").astype("int32")
                    if RIDEABLE_COL in chunk.columns:
                        df["electric"] = (chunk.loc[ok, RIDEABLE_COL].str.strip() == "electric_bike").astype("int32")
                    else:
                        df["electric"] = 0
                    df["cnt"] = 1
                    parts.append(df.groupby("hour", sort=False)[["cnt", "member", "casual", "electric"]].sum())
    if not parts:
        raise ValueError(f"{path.name}: no CSV members")
    out = pd.concat(parts).groupby(level=0).sum()
    return out, stats


def aggregate_all(zips: list[Path]) -> tuple[pd.DataFrame, list[dict]]:
    frames, all_stats = [], []
    for p in zips:
        df, st = aggregate_zip(p)
        print(f"[trips] {p.name}: {st['rows']:,} rows ({st['schema']}), unparsed={st['unparsed_rows']}")
        frames.append(df)
        all_stats.append(st)
    hourly = pd.concat(frames).groupby(level=0).sum().sort_index()
    hourly.index = pd.to_datetime(hourly.index, format="%Y-%m-%d %H")
    hourly.index.name = "ts_local"
    return hourly, all_stats
