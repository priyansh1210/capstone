"""Benchmark policies are isolated and start from identical conditions."""

import numpy as np

from amm.engine import train_initial
from amm.storage.store import Store
from conftest import make_scenario, make_session, small_cfg


def _preds(store, rid):
    return store.query("SELECT seq, y_pred, model_version FROM predictions WHERE run_id=? AND role='active' ORDER BY seq", (rid,))


def test_policies_share_nothing_mutable(store, tmp_path):
    sc = make_scenario(change_day=2)
    cfg = small_cfg()
    init = train_initial(sc, cfg)
    sessions = {p: make_session(sc, p, cfg, store, tmp_path, initial=init, run_id=f"{p}-iso") for p in ("static", "periodic", "adaptive")}
    objs = lambda s: [s.sim, s.sim.view, s.controller, s.controller.monitor, s.controller.registry, s.controller.registry.model("v001")]  # noqa: E731
    ids = [id(o) for s in sessions.values() for o in objs(s)]
    assert len(ids) == len(set(ids))
    # identical starting model behaviour
    X = sc.replay.iloc[:48]
    p0 = [s.controller.registry.model("v001").predict(X) for s in sessions.values()]
    for p in p0[1:]:
        np.testing.assert_allclose(p0[0], p)
    for s in sessions.values():
        s.run()
    # the static run is unaffected by the others retraining
    st = _preds(store, "static-iso")
    assert (st["model_version"] == "v001").all()


def test_running_alongside_other_policies_does_not_change_results(tmp_path):
    sc = make_scenario(change_day=2)
    cfg = small_cfg()
    init = train_initial(sc, cfg)
    a = Store(tmp_path / "a.sqlite")
    alone = make_session(sc, "adaptive", cfg, a, tmp_path / "a", initial=init, run_id="ad")
    alone.run()
    b = Store(tmp_path / "b.sqlite")
    other = make_session(sc, "periodic", cfg, b, tmp_path / "b", initial=init, run_id="pe")
    mixed = make_session(sc, "adaptive", cfg, b, tmp_path / "b", initial=init, run_id="ad")
    while not (other.finished and mixed.finished):  # interleaved, lock-step
        other.step()
        mixed.step()
    pa, pb = _preds(a, "ad"), _preds(b, "ad")
    np.testing.assert_allclose(pa["y_pred"], pb["y_pred"])
    assert list(pa["model_version"]) == list(pb["model_version"])
    assert [e["action"] for e in alone.controller.events] == [e["action"] for e in mixed.controller.events]
