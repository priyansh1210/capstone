"""Filesystem layout. Everything is relative to the project root so the
project works from any checkout location."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("AMM_ROOT")
    if env:
        return Path(env).resolve()
    # src/amm/paths.py -> project root is two levels above src/
    return Path(__file__).resolve().parents[2]


ROOT = project_root()
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW_TRIPS = RAW / "capitalbikeshare"
RAW_WEATHER = RAW / "noaa_isd_lite"
RAW_UCI = RAW / "uci_bike_sharing"
MANUAL = RAW / "manual"
PROCESSED = DATA / "processed"
SCENARIOS = DATA / "scenarios"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"
CONFIGS = ROOT / "configs"


def ensure_dirs() -> None:
    for p in (RAW_TRIPS, RAW_WEATHER, RAW_UCI, MANUAL, PROCESSED, SCENARIOS, ARTIFACTS, REPORTS):
        p.mkdir(parents=True, exist_ok=True)
