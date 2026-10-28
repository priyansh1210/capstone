"""Validation gate: honest rejection of an inferior candidate; promotion on held-out rows."""

import json

import numpy as np

from conftest import actions, make_scenario, make_session, small_cfg


def test_inferior_candidate_is_rejected_and_current_model_kept(store, tmp_path):
    sc = make_scenario()
    cfg = small_cfg(policy={"periodic_interval_batches": 5})
    s = make_session(sc, "periodic", cfg, store, tmp_path)
    s.inject_weak_candidates()  # TEST-ONLY: next cycle trains only a deliberately weak model
    s.run(max_steps=8)
    acts = actions(s)
    assert "FAULT_INJECTION" in acts and "CANDIDATES_REJECTED" in acts
    rej = next(e for e in s.controller.events if e["action"] == "CANDIDATES_REJECTED")
    assert rej["fault_injection"] is True
    cand = rej["measurements"]["candidates"][0]
    assert cand["model"] == "weak_hgb" and cand["passed"] is False and cand["rel_improvement"] < 0
    assert s.controller.registry.active_id == "v001"
    rejected = [v for v in s.controller.registry.versions.values() if v.status == "rejected"]
    assert rejected and rejected[0].fault_injection


def test_better_candidate_is_promoted_using_held_out_rows(store, tmp_path):
    sc = make_scenario(change_day=1, factor=2.5)
    cfg = small_cfg(policy={"periodic_interval_batches": 12}, retraining={"windows_days": [7]})
    s = make_session(sc, "periodic", cfg, store, tmp_path)
    s.run(max_steps=14)
    assert "PROMOTED" in actions(s), actions(s)
    reg = s.controller.registry
    new = reg.active
    old = reg.versions["v001"]
    assert new.version != "v001" and old.status == "previous"  # kept as fallback during probation
    # validation rows were after the old model's fit/selection data, training rows before validation
    assert new.val_end_seq > old.selection_end_seq
    cyc = store.query("SELECT * FROM cycles WHERE run_id=?", (s.run_id,)).iloc[0]
    assert new.train_end < new.val_start
    assert cyc["best_val_mae"] <= cyc["current_val_mae"] * (1 - cfg["retraining"]["min_rel_improvement"])
    cands = store.query("SELECT * FROM candidates WHERE run_id=?", (s.run_id,))
    assert cands["promoted"].sum() == 1 and (cands["passed"] == 1).any()
    ev = next(e for e in s.controller.events if e["action"] == "PROMOTED")
    assert ev["thresholds"]["min_rel_improvement"] == 0.05
    rec = json.loads(store.query("SELECT record FROM model_versions WHERE run_id=? AND version=?", (s.run_id, new.version))["record"][0])
    assert rec["n_val"] >= cfg["retraining"]["min_validation_hours"] and np.isfinite(rec["val_mae"])
