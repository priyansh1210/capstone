"""Candidate training and the validation gate (shared by periodic and adaptive).

Leakage rules enforced here:
* Only labels already revealed (the ControllerView) are used.
* The validation window is the newest ``validation_hours`` labelled rows that
  lie strictly *after* everything the current model was fitted or selected on
  (``selection_end_seq``). If fewer than ``min_validation_hours`` such rows
  exist, the cycle waits.
* Each candidate's training window ends strictly *before* the validation
  window starts, so neither compared model was fitted on validation rows.
* Suspected outage hours (runs of zero trips in revealed labels) are excluded
  from fitting but kept in validation scoring.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from amm.data.quality import outage_mask
from amm.metrics import summarize
from amm.models.candidates import make_model
from amm.stream.view import Labelled


@dataclass
class Plan:
    val_idx: np.ndarray
    train_idx: dict  # window_days -> index array
    val_start: str
    val_end: str
    val_end_seq: int
    note: str = ""


@dataclass
class Candidate:
    name: str
    window_days: int
    n_train: int
    train_start: str | None
    train_end: str | None
    train_end_seq: int
    seconds: float
    model: object = None
    error: str | None = None
    val: dict = field(default_factory=dict)
    rel_improvement: float | None = None
    passed: bool = False


def plan_cycle(data: Labelled, selection_end_seq: int, cfg: dict) -> tuple[Plan | None, str]:
    rc = cfg["retraining"]
    eligible = np.flatnonzero(data.seq > selection_end_seq)
    if len(eligible) < rc["min_validation_hours"]:
        return None, (
            f"insufficient validation labels after current model's cutoff: "
            f"{len(eligible)} < {rc['min_validation_hours']} hours"
        )
    val_idx = eligible[-rc["validation_hours"]:]
    first_val = val_idx[0]
    val_start_ts = data.ts[first_val]
    before = np.arange(first_val)  # strictly earlier rows
    keep = ~outage_mask(data.y[:first_val])
    train_idx = {}
    for w in rc["windows_days"]:
        lo = val_start_ts - np.timedelta64(int(w), "D")
        idx = before[(data.ts[before] >= lo) & keep]
        if len(idx) >= rc["min_train_hours"]:
            train_idx[int(w)] = idx
    if not train_idx:
        return None, f"insufficient training labels before validation window (< {rc['min_train_hours']} hours)"
    return (
        Plan(
            val_idx=val_idx,
            train_idx=train_idx,
            val_start=str(pd.Timestamp(val_start_ts)),
            val_end=str(pd.Timestamp(data.ts[val_idx[-1]])),
            val_end_seq=int(data.seq[val_idx[-1]]),
        ),
        "ok",
    )


def fit_candidates(data: Labelled, plan: Plan, names: list[str], seed: int, threads: int, fail: set | None = None) -> list[Candidate]:
    out = []
    for w, idx in plan.train_idx.items():
        sub = data.take(idx)
        for name in names:
            c = Candidate(
                name, w, len(idx), str(pd.Timestamp(sub.ts[0])), str(pd.Timestamp(sub.ts[-1])), int(sub.seq[-1]), 0.0
            )
            t0 = time.perf_counter()
            try:
                if fail and name in fail:
                    raise RuntimeError(f"injected training failure for {name}")
                params = {"n_jobs": threads} if name in ("rf", "weak_rf") else None
                with threadpool_limits(threads):
                    c.model = make_model(name, seed=seed, params=params).fit(sub.X, sub.y)
            except Exception as exc:
                c.error = f"{type(exc).__name__}: {exc}"
                c.model = None
                traceback.print_exc(limit=1)
            c.seconds = time.perf_counter() - t0
            out.append(c)
    return out


def evaluate(current_model, candidates: list[Candidate], data: Labelled, plan: Plan, cfg: dict) -> dict:
    rc = cfg["retraining"]
    v = data.take(plan.val_idx)
    cur = summarize(v.y, current_model.predict(v.X))
    best = None
    for c in candidates:
        if c.model is None:
            continue
        try:
            c.val = summarize(v.y, c.model.predict(v.X))
        except Exception as exc:
            c.error = f"validation failed: {exc}"
            c.model = None
            continue
        c.rel_improvement = (cur["mae"] - c.val["mae"]) / cur["mae"] if cur["mae"] else 0.0
        c.passed = len(v) >= rc["min_validation_hours"] and c.rel_improvement >= rc["min_rel_improvement"]
        if c.passed and (best is None or c.val["mae"] < best.val["mae"]):
            best = c
    return {
        "n_val": len(v),
        "current": cur,
        "winner": best,
        "thresholds": {
            "min_rel_improvement": rc["min_rel_improvement"],
            "min_validation_hours": rc["min_validation_hours"],
        },
    }
