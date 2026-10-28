"""Small deterministic fixtures (scenario E): tiny generated streams, a fast
test configuration and helpers. No downloaded data is needed for most tests."""

from __future__ import annotations

import pandas as pd
import pytest

from amm.config import deep_merge, load_config
from amm.data import synthetic
from amm.data.scenarios import Scenario
from amm.engine import Session, train_initial
from amm.storage.store import Store

TEST_OVERRIDES = {
    "frozen_policy_file": None,
    "seed": 3,
    "initial_model": {"name": "ridge", "window_days": None},
    "stream": {"label_delay_batches": 1},
    "monitor": {"adwin_delta": 0.002, "adwin_clock": 24, "rolling_hours": 48, "warm_start_hours": 72},
    "policy": {
        "deterioration": {"recent_hours": 72, "rel_margin": 0.15, "abs_margin": 0.0, "confirm_checks": 2, "investigate_max_batches": 5},
        "cooldown_batches": 3,
        "budget_cycles": 10,
        "periodic_interval_batches": 6,
    },
    "retraining": {
        "models": ["ridge"],
        "windows_days": [14],
        "validation_hours": 72,
        "min_validation_hours": 48,
        "min_train_hours": 120,
        "min_rel_improvement": 0.05,
        "threads": 1,
    },
    "probation": {"window_hours": 24, "max_windows": 3, "rollback_rel_margin": 0.05, "consecutive_windows": 2},
    "storage": {"persist_artifacts": True},
}


def small_cfg(**extra) -> dict:
    return load_config(overrides=deep_merge(TEST_OVERRIDES, extra))


def make_scenario(n_train=56, n_cal=14, n_rep=36, seed=0, change_day=None, factor=2.5, hours=None) -> Scenario:
    change = None
    if change_day is not None:
        start = pd.Timestamp(synthetic.START) + pd.Timedelta(days=n_train + n_cal + change_day)
        change = {"start": str(start), "factor": factor, "hours": hours or list(range(24)), "workingday_only": False}
    df = synthetic.generate(seed, n_train + n_cal + n_rep, change=change)
    day = (df["ts_local"] - df["ts_local"].iloc[0]).dt.days
    tr = df[day < n_train].copy()
    cal = df[(day >= n_train) & (day < n_train + n_cal)].copy()
    rep = df[day >= n_train + n_cal].copy()
    return Scenario("fixture", "generated", "test fixture", tr, cal, rep, {"seed": seed, "change": change})


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()


def make_session(sc, policy, cfg, store, tmp_path, initial=None, run_id=None) -> Session:
    return Session(sc, policy, cfg, store, run_id=run_id or f"{policy}-test", initial=initial or train_initial(sc, cfg), artifact_root=tmp_path / "art")


def actions(session) -> list[str]:
    return [e["action"] for e in session.controller.events]
