"""Target-leaking columns can never reach a model; weather is lagged; no backward fill."""

import numpy as np
import pandas as pd
import pytest

from amm.data import weather
from amm.data.features import EXCLUDED, FEATURES, TARGET, assert_no_leakage
from amm.models.candidates import make_model
from conftest import make_scenario


def test_feature_list_excludes_leaky_columns():
    for col in ["cnt", "member", "casual", "electric", "instant", "suspected_outage", "scenario", "ts_local"]:
        assert col not in FEATURES
        assert col in EXCLUDED
    assert_no_leakage(FEATURES)
    with pytest.raises(ValueError):
        assert_no_leakage(FEATURES + ["casual"])
    with pytest.raises(ValueError):
        assert_no_leakage(FEATURES + ["cnt_lag_1"])  # unknown/derived columns are rejected too


@pytest.mark.parametrize("name", ["ridge", "rf", "hgb"])
def test_models_ignore_leaky_columns(name):
    sc = make_scenario(n_train=20, n_cal=2, n_rep=2)
    df = sc.train.copy()
    df["casual"] = df[TARGET] * 0.3
    df["member"] = df[TARGET] - df["casual"]
    m = make_model(name, seed=0, params={"n_jobs": 1} if name == "rf" else None).fit(df, df[TARGET])
    p1 = m.predict(df)
    shuffled = df.copy()
    rng = np.random.default_rng(0)
    for c in ["casual", "member", "instant", "seq", "cnt"]:
        shuffled[c] = rng.permutation(shuffled[c].to_numpy())
    np.testing.assert_allclose(p1, m.predict(shuffled))
    assert (p1 >= 0).all()


def test_weather_is_lagged_and_never_backfilled():
    # UTC observations whose temperature equals the UTC hour index
    idx = pd.date_range("2018-06-01 00:00", periods=48, freq="h", tz="UTC")
    w = pd.DataFrame({c: np.nan for c in weather.CONTINUOUS + ["precip_1h_mm", "weathersit"]}, index=idx)
    w["temp_c"] = np.arange(48, dtype=float)
    w.loc[idx[20:30], "temp_c"] = np.nan  # a 10-hour gap
    w["weathersit"] = 1.0
    local = pd.date_range("2018-06-01 06:00", periods=30, freq="h")  # EDT = UTC-4
    feats, _ = weather.lagged_weather_for_local_hours(w, local, "America/New_York", lag_hours=1, max_ffill_hours=3)
    # local 06:00 EDT = 10:00 UTC; the usable observation is the one from 09:00 UTC
    assert feats.loc[pd.Timestamp("2018-06-01 06:00"), "temp_c"] == 9.0
    # inside the gap: carried forward for at most 3 hours from *earlier* values, then missing
    t_gap = feats.loc[pd.Timestamp("2018-06-01 18:00"), "temp_c"]  # 22:00 UTC -> obs 21:00 UTC (in gap) -> carried from 19:00
    assert t_gap == 19.0
    assert np.isnan(feats.loc[pd.Timestamp("2018-06-01 21:00"), "temp_c"])  # obs 00:00 UTC: gap longer than 3 h -> missing
    # no value ever comes from the future
    for t, v in feats["temp_c"].dropna().items():
        obs_utc_hour = (t + pd.Timedelta(hours=4) - pd.Timedelta(hours=1) - pd.Timestamp("2018-06-01")).total_seconds() / 3600
        assert v <= obs_utc_hour
