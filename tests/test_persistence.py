"""Checkpoint/reload equivalence and absence of duplicate processing."""

import numpy as np
import pytest

from amm.engine import DuplicateStepError, Session, train_initial
from amm.models.registry import Registry
from amm.storage.store import Store
from conftest import make_scenario, make_session, small_cfg


def _dump(store, rid):
    p = store.query("SELECT seq, role, model_version, y_pred, y_true FROM predictions WHERE run_id=? ORDER BY seq, role", (rid,))
    d = store.query("SELECT step, action FROM decisions WHERE run_id=? ORDER BY event_id", (rid,))
    return p, d


def test_checkpoint_resume_equals_uninterrupted_run(tmp_path):
    sc = make_scenario(change_day=2)
    cfg = small_cfg()
    init = train_initial(sc, cfg)
    ref_store = Store(tmp_path / "ref.sqlite")
    ref = make_session(sc, "adaptive", cfg, ref_store, tmp_path / "ref", initial=init, run_id="r")
    ref.run()

    st = Store(tmp_path / "ck.sqlite")
    s = make_session(sc, "adaptive", cfg, st, tmp_path / "ck", initial=init, run_id="r")
    s.run(max_steps=12)
    s.save(tmp_path / "ck.joblib")
    s.run(max_steps=7)  # DB now ahead of the checkpoint (e.g. app crashed before saving)
    st.close()

    st2 = Store(tmp_path / "ck.sqlite")
    s2 = Session.load(tmp_path / "ck.joblib", st2)
    assert s2.t == 12 and st2.last_step("r") == 11  # rewound to the checkpoint
    s2.run()
    p_ref, d_ref = _dump(ref_store, "r")
    p_ck, d_ck = _dump(st2, "r")
    assert len(p_ck) == len(p_ref)  # no duplicate prediction rows
    np.testing.assert_allclose(p_ck["y_pred"], p_ref["y_pred"])
    np.testing.assert_allclose(p_ck["y_true"], p_ref["y_true"])
    assert list(d_ck["action"]) == list(d_ref["action"])
    n = st2.query("SELECT COUNT(*) n, COUNT(DISTINCT step) d FROM steps WHERE run_id='r'")
    assert int(n["n"][0]) == int(n["d"][0]) == s2.sim.total_steps


def test_a_step_cannot_be_recorded_twice(store, tmp_path):
    sc = make_scenario()
    s = make_session(sc, "static", small_cfg(), store, tmp_path)
    s.run(max_steps=3)
    s.sim.t = 1  # simulate a stale in-memory session trying to redo step 1
    with pytest.raises(DuplicateStepError):
        s.step()


def test_artifacts_reload(store, tmp_path):
    sc = make_scenario()
    s = make_session(sc, "static", small_cfg(), store, tmp_path)
    v = s.controller.registry.active
    assert v.artifact and v.artifact.endswith("v001.joblib")
    m = Registry.load_artifact(v.artifact)
    X = sc.replay.iloc[:24]
    np.testing.assert_allclose(m.predict(X), s.controller.registry.model("v001").predict(X))
