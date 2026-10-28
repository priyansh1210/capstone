"""Failures in training or saving leave a usable current model."""

from conftest import actions, make_scenario, make_session, small_cfg


def test_training_failure_keeps_current_model(store, tmp_path):
    sc = make_scenario(change_day=1)
    s = make_session(sc, "periodic", small_cfg(policy={"periodic_interval_batches": 5}), store, tmp_path)
    s.controller.fault["fail_training"] = {"ridge"}
    s.run()
    assert "TRAINING_FAILED" in actions(s)
    assert s.controller.registry.active_id == "v001"
    p = store.query("SELECT COUNT(*) n, SUM(y_true IS NULL) u FROM predictions WHERE run_id=?", (s.run_id,))
    assert int(p["n"][0]) == len(sc.replay) and int(p["u"][0]) == 0  # kept serving and scoring


def test_artifact_save_failure_aborts_promotion(store, tmp_path):
    sc = make_scenario(change_day=1, factor=2.5)
    cfg = small_cfg(policy={"periodic_interval_batches": 12}, retraining={"windows_days": [7]})
    s = make_session(sc, "periodic", cfg, store, tmp_path)
    s.controller.fault["fail_save"] = True
    s.run(max_steps=14)
    assert "PROMOTION_FAILED" in actions(s) and "PROMOTED" not in actions(s)
    reg = s.controller.registry
    assert reg.active_id == "v001" and reg.previous_id is None
    failed = [v for v in reg.versions.values() if v.status == "failed"]
    assert failed and "save failure" in failed[0].notes
    s.run()  # still serving afterwards
    assert s.finished


def test_real_save_error_is_caught(store, tmp_path, monkeypatch):
    from amm.models import registry as reg_mod

    sc = make_scenario(change_day=1, factor=2.5)
    cfg = small_cfg(policy={"periodic_interval_batches": 12}, retraining={"windows_days": [7]})
    s = make_session(sc, "periodic", cfg, store, tmp_path)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(reg_mod.joblib, "dump", boom)
    s.run(max_steps=14)
    assert "PROMOTION_FAILED" in actions(s)
    assert s.controller.registry.active_id == "v001"
