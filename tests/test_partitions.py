"""Chronological partitions, preprocessing boundaries and retraining windows."""

import numpy as np
import pandas as pd
import pytest

from amm.data.dataset import split_partitions
from amm.data.features import FEATURES, TARGET
from amm.models.candidates import make_model
from amm.policy.retrain import plan_cycle
from conftest import make_scenario, small_cfg


def _frame():
    ts = pd.date_range("2015-01-01", "2018-12-31 23:00", freq="h")
    return pd.DataFrame({"ts_local": ts, "instant": np.arange(len(ts))})


def test_partitions_are_chronological_and_disjoint():
    parts = split_partitions(_frame(), {"train": ["2015-01-01", "2016-12-31"], "calibration": ["2017-01-01", "2017-12-31"], "replay": ["2018-01-01", "2018-12-31"]})
    tr, cal, rep = parts["train"], parts["calibration"], parts["replay"]
    assert tr["ts_local"].max() < cal["ts_local"].min()
    assert cal["ts_local"].max() < rep["ts_local"].min()
    assert tr["ts_local"].max() == pd.Timestamp("2016-12-31 23:00")  # inclusive end day
    assert len(set(tr["instant"]) & set(rep["instant"])) == 0


def test_overlapping_partitions_are_rejected():
    with pytest.raises(ValueError):
        split_partitions(_frame(), {"train": ["2015-01-01", "2017-06-30"], "calibration": ["2017-01-01", "2017-12-31"], "replay": ["2018-01-01", "2018-12-31"]})


def test_preprocessing_is_fitted_on_training_rows_only():
    sc = make_scenario(n_train=30, n_cal=5, n_rep=5)
    train = sc.train
    m = make_model("ridge", seed=0).fit(train[FEATURES], train[TARGET])
    scaler = m.model_.regressor_.named_steps["pre"].named_transformers_["num"][-1]
    num_cols = m.model_.regressor_.named_steps["pre"].transformers_[1][2]
    np.testing.assert_allclose(scaler.mean_, train[num_cols].astype(float).mean().to_numpy(), rtol=1e-6)
    # a different (later) window gives different statistics: nothing leaks across windows
    m2 = make_model("ridge", seed=0).fit(sc.calibration[FEATURES], sc.calibration[TARGET])
    s2 = m2.model_.regressor_.named_steps["pre"].named_transformers_["num"][-1]
    assert not np.allclose(scaler.mean_, s2.mean_)


def test_retraining_windows_precede_validation_and_follow_cutoff():
    from amm.stream.view import Labelled

    sc = make_scenario(n_train=40, n_cal=10, n_rep=20)
    hist = pd.concat([sc.history, sc.replay.iloc[: 24 * 8]], ignore_index=True)
    data = Labelled(hist[FEATURES], hist[TARGET].to_numpy(float), hist["seq"].to_numpy(), hist["ts_local"].to_numpy("datetime64[ns]"))
    cfg = small_cfg()
    cutoff = int(sc.calibration["seq"].max())
    plan, why = plan_cycle(data, cutoff, cfg)
    assert plan is not None, why
    val_seq = data.seq[plan.val_idx]
    assert val_seq.min() > cutoff  # validation strictly after the current model's fit/selection data
    assert len(val_seq) <= cfg["retraining"]["validation_hours"]
    for idx in plan.train_idx.values():
        assert data.seq[idx].max() < val_seq.min()  # candidates never see validation rows
        assert len(set(idx) & set(plan.val_idx)) == 0
    # not enough labels after the cutoff -> wait
    plan2, why2 = plan_cycle(data, int(data.seq[-10]), cfg)
    assert plan2 is None and "insufficient validation labels" in why2
