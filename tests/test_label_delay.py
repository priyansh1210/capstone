"""Delayed-label availability and stored original predictions."""

import numpy as np

from conftest import make_scenario, make_session, small_cfg


def test_labels_become_visible_only_after_the_delay(store, tmp_path):
    sc = make_scenario()
    cfg = small_cfg(stream={"label_delay_batches": 2})
    s = make_session(sc, "static", cfg, store, tmp_path)
    hist_max = int(sc.history["seq"].max())
    for t in range(8):
        s.step()
        lab = s.sim.view.labelled()
        r = t - 2  # batch whose labels were revealed at step t
        expected = hist_max if r < 0 else int(s.sim._seq[s.sim.batch_slice(r)].max())
        assert int(lab.seq.max()) == expected
        # covariates of the batch predicted at step t are observed, the next batch's are not
        assert len(s.controller.pending) == min(t + 1, 2)


def test_predictions_are_stored_with_original_version_and_scored_as_made(store, tmp_path):
    sc = make_scenario()
    cfg = small_cfg()
    s = make_session(sc, "static", cfg, store, tmp_path)
    s.run(max_steps=6)
    assert s.force_activate_weak()  # changes the active model at step 6 (test-only)
    s.run()
    p = store.query("SELECT * FROM predictions WHERE run_id=? AND role='active' ORDER BY seq", (s.run_id,))
    assert p["y_true"].notna().all(), "every prediction is scored once its label arrives"
    assert (p["label_reveal_step"] == p["prediction_step"] + 1).all()
    early = p[p["prediction_step"] < 6]
    assert (early["model_version"] == "v001").all()  # never re-attributed to the newer model
    later = p[p["prediction_step"] == 6]
    assert (later["model_version"] == "v002").all()
    # the stored error is the error of the stored prediction, not a recomputation
    np.testing.assert_allclose(p["abs_err"], np.abs(p["y_true"] - p["y_pred"]))
    # the stored rows of step 6 are the weak model's outputs, not what v001 would have predicted
    rows = sc.replay.set_index("seq").loc[later["seq"]]
    v001 = s.controller.registry.model("v001")
    assert not np.allclose(later["y_pred"].to_numpy(), v001.predict(rows))


def test_every_row_scored_exactly_once(store, tmp_path):
    sc = make_scenario(n_rep=10)
    s = make_session(sc, "static", small_cfg(), store, tmp_path)
    s.run()
    n = store.query("SELECT COUNT(*) n, COUNT(DISTINCT seq) d, SUM(y_true IS NULL) u FROM predictions WHERE run_id=?", (s.run_id,))
    assert int(n["n"][0]) == len(sc.replay) == int(n["d"][0])
    assert int(n["u"][0]) == 0
    assert s.finished and s.t == s.sim.n_batches + 1  # one drain step for delay=1
