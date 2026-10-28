"""The prediction-input contract.

Only columns listed in ``FEATURES`` may ever reach a model. Everything in
``EXCLUDED`` is kept in the dataset for traceability or evaluation but is
forbidden as an input, and ``assert_no_leakage`` enforces that.
"""

from __future__ import annotations

TARGET = "cnt"

CALENDAR = ["hr", "weekday", "workingday", "holiday", "mnth", "season", "yr"]
# Weather observed at DCA in the hour *before* the target hour (lag 1 h).
WEATHER = [
    "temp_c",
    "atemp_c",
    "humidity",
    "windspeed_ms",
    "pressure_hpa",
    "cloud_cover",
    "precip_1h_mm",
    "weathersit",
]
FEATURES = CALENDAR + WEATHER

CATEGORICAL = ["hr", "weekday", "mnth", "season", "weathersit"]

EXCLUDED = {
    "cnt": "target",
    "member": "member + casual == cnt (target leak; analogue of UCI 'registered')",
    "casual": "member + casual == cnt (target leak)",
    "electric": "derived from the unrevealed target (count of e-bike trips)",
    "instant": "row identifier, kept for traceability only",
    "ts_local": "timestamp; calendar features are derived from it instead",
    "dewpoint_c": "redundant with humidity/temp (kept for reference)",
    "suspected_outage": "derived from the target (runs of zero trips)",
    "scenario": "scenario identity must never be an input",
}


def assert_no_leakage(columns) -> None:
    cols = set(columns)
    bad = cols & set(EXCLUDED)
    unknown = cols - set(FEATURES)
    if bad or unknown:
        raise ValueError(f"forbidden model inputs: excluded={sorted(bad)} unknown={sorted(unknown)}")
