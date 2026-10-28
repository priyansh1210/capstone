"""Rollback uses paired, subsequent predictions; a shared rise in error is not a reason."""

import numpy as np

from amm.policy.probation import Probation
from conftest import actions, make_scenario, make_session, small_cfg


def test_weak_activation_is_rolled_back_on_paired_evidence(store, tmp_path):
    sc = make_scenario()
    s = make_session(sc, "adaptive", small_cfg(), store, tmp_path)
    s.run(max_steps=5)
    assert s.force_activate_weak()  # TEST-ONLY activation without validation (disclosed)
    weak = s.controller.registry.active_id
    s.run(max_steps=6)
    acts = actions(s)
    assert "FAULT_INJECTION_ACTIVATION" in acts and "ROLLED_BACK" in acts
    reg = s.controller.registry
    assert reg.active_id == "v001" and reg.versions[weak].status == "rolled_back"
    rb = next(e for e in s.controller.events if e["action"] == "ROLLED_BACK")
    wins = rb["measurements"]["windows"]
    assert len(wins) >= 2 and all(w["new_worse"] for w in wins[-2:])
    # the paired evidence comes from shadow predictions on exactly the same rows,
    # made before their labels were revealed
    p = store.query("SELECT seq, role, model_version, prediction_step, label_reveal_step FROM predictions WHERE run_id=? AND prediction_step>=5", (s.run_id,))
    shadow = p[p["role"] == "shadow"]
    active = p[(p["role"] == "active") & p["seq"].isin(shadow["seq"])]
    assert len(shadow) > 0 and set(shadow["seq"]) == set(active["seq"])
    assert (shadow["model_version"] == "v001").all() and (active["model_version"] == weak).all()
    assert (shadow["prediction_step"] < shadow["label_reveal_step"]).all()
    # cooldown restarts at rollback (no immediate promote/rollback loop)
    assert s.controller.last_cycle_step == rb["step"]


def _cfg():
    return {"probation": {"window_hours": 24, "max_windows": 3, "rollback_rel_margin": 0.05, "consecutive_windows": 2}}


def test_shared_error_increase_does_not_cause_rollback():
    rng = np.random.default_rng(0)
    pb = Probation("v2", "v1", 0, _cfg())
    for day in range(3):
        y = rng.poisson(300, 24).astype(float) * (1 + day)  # demand shock grows: both models get much worse
        yhat = np.full(24, 300.0)
        noise = rng.normal(0, 1, 24)
        pb.add(y, yhat + noise, yhat - noise)  # paired errors statistically equal
    assert pb.decision == "keep"
    s = pb.summary()
    assert s["mae_new"] > 100 and abs(s["mae_new"] - s["mae_prev"]) / s["mae_prev"] < 0.05


def test_one_bad_window_is_not_enough():
    pb = Probation("v2", "v1", 0, _cfg())
    y = np.full(24, 100.0)
    pb.add(y, y * 1.5, y * 1.01)  # new clearly worse in window 1 ...
    pb.add(y, y * 1.01, y * 1.02)  # ... but not in window 2
    pb.add(y, y * 1.5, y * 1.01)  # worse again in window 3 (not consecutive)
    assert pb.decision == "keep" and [w["new_worse"] for w in pb.windows] == [True, False, True]
