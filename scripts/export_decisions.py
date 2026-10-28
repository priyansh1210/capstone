"""Export decision logs and model-version references from per-run SQLite stores to small
CSV files that can be committed (the stores themselves are gitignored).

    .venv\\Scripts\\python scripts\\export_decisions.py [reports\\multicity] [--labels adaptive probe ...]

Writes <out>/decisions/<run_id>.csv (every logged decision with its measurements) and
<out>/decisions/<run_id>.versions.csv (each model version with its reference values).
Read-only on the stores.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_LABELS = ["adaptive", "adaptive-bias", "adaptive-ph", "adaptive-kswin", "probe", "periodic-28"]
VERSION_KEYS = ["model_name", "window_days", "train_start", "train_end", "val_start", "val_end", "val_mae", "current_val_mae",
                "reference_signal", "reference_mae", "reference_source", "activated_step", "retired_step"]


def export(out: Path, labels: list[str], synthetic: bool = False) -> int:
    runs = sorted((out / "runs").glob("*.sqlite"))
    dest = out / "decisions"
    dest.mkdir(exist_ok=True)
    n = 0
    for db in runs:
        rid = db.stem
        label = next((lab for lab in sorted(labels, key=len, reverse=True) if rid.startswith(lab + "-")), None)
        if label is None or ("synthetic" in rid and not synthetic):
            continue
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            dec = pd.read_sql_query("SELECT step, ts, state_from, state_to, action, reason, measurements, thresholds FROM decisions "
                                    "WHERE run_id=? ORDER BY event_id", con, params=(rid,))
            ver = pd.read_sql_query("SELECT version, status, created_step, record FROM model_versions WHERE run_id=? ORDER BY created_step",
                                    con, params=(rid,))
        finally:
            con.close()
        dec = dec[dec["action"] != "PROBATION_CHECK"]
        dec.to_csv(dest / f"{rid}.csv", index=False)
        rows = []
        for _, v in ver.iterrows():
            rec = json.loads(v["record"]) if isinstance(v["record"], str) else {}
            rows.append({"version": v["version"], "created_step": v["created_step"], "status_final": v["status"],
                         **{k: rec.get(k) for k in VERSION_KEYS}})
        pd.DataFrame(rows).to_csv(dest / f"{rid}.versions.csv", index=False)
        n += 1
    print(f"exported {n} runs to {dest}")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="reports/multicity")
    ap.add_argument("--labels", nargs="*", default=DEFAULT_LABELS)
    ap.add_argument("--include-synthetic", action="store_true")
    a = ap.parse_args()
    export(Path(a.out), a.labels, a.include_synthetic)
