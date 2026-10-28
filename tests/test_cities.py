"""Multi-city plumbing: city registry, scenarios, automatic replay end, oracle steps."""

from dataclasses import replace

import pandas as pd

from amm import paths
from amm.data import cities, scenarios, synthetic
from conftest import TEST_OVERRIDES, small_cfg


def _fake_city(tmp_path, monkeypatch):
    df = synthetic.generate(0, 70, start="2014-01-01").drop(columns=["seq"])
    df.loc[df["ts_local"] >= "2014-03-10", "temp_c"] = float("nan")  # weather stops early (like DC 2025)
    monkeypatch.setattr(paths, "PROCESSED", tmp_path)
    (tmp_path / "chicago").mkdir()
    df.to_parquet(tmp_path / "chicago" / "hourly.parquet", index=False)
    c = replace(cities.CITIES["chicago"], partitions={"train": ["2014-01-01", "2014-01-31"], "calibration": ["2014-02-01", "2014-02-14"], "replay": ["2014-02-15", "auto"]})
    monkeypatch.setitem(cities.CITIES, "chicago", c)
    return df


def test_city_selection_rules():
    c = cities.CITIES
    assert c["nyc"].wants("2019-citibike-tripdata.zip") and not c["nyc"].wants("JC-201901-citibike-tripdata.csv.zip")
    assert not c["nyc"].wants("2013-citibike-tripdata.zip")  # outside the configured years
    assert c["chicago"].wants("Divvy_Trips_2019_Q2.zip") and c["chicago"].wants("202004-divvy-tripdata.zip")
    assert c["sf"].wants("202211-baywheeels-tripdata.csv.zip")  # typo in the operator's file name
    assert not c["sf"].wants("index.html")


def test_city_scenario_hidden_change_and_auto_end(tmp_path, monkeypatch):
    _fake_city(tmp_path, monkeypatch)
    cfg = small_cfg(scenarios={"city_abrupt": {"offset_days": 5, "factor": 2.0, "hours": [8], "workingday_only": False}})
    sc = scenarios.build("city_chicago_abrupt", cfg)
    assert sc.kind == "modified" and sc.manifest["city"] == "chicago"
    assert sc.manifest["change"]["start"] == "2014-02-20" and sc.manifest["change"]["rows_modified"] > 0
    assert sc.replay["ts_local"].max() == pd.Timestamp("2014-03-08 23:00")  # last full day with observed weather
    un = scenarios.build("city_chicago_unmodified", cfg)
    assert un.kind == "source" and un.manifest["change"] is None


def test_oracle_requests_are_computed_on_the_evaluator_side(tmp_path, monkeypatch):
    from amm.config import deep_merge
    from amm.experiments.runner import run_job

    _fake_city(tmp_path, monkeypatch)
    ov = deep_merge(TEST_OVERRIDES, {"storage": {"persist_artifacts": False}, "retraining": {"windows_days": [7]},
                                     "scenarios": {"city_abrupt": {"offset_days": 3, "factor": 2.5, "hours": list(range(24)), "workingday_only": False}}})
    res = run_job({"config": None, "overrides": ov, "scenario": "city_chicago_abrupt", "seed": None, "policies": ["oracle"],
                   "out_dir": str(tmp_path / "out"), "tag": "t-", "label": "oracle", "oracle_offsets": [8]})
    r = res[0]
    assert "error" not in r, r.get("error")
    assert r["label"] == "oracle" and r["city"] == "chicago" and r["cycles"] == 1 and r["first_retrain_days"] == 8
    # the oracle is never run where no change exists
    assert run_job({"config": None, "overrides": ov, "scenario": "city_chicago_unmodified", "seed": None, "policies": ["oracle"],
                    "out_dir": str(tmp_path / "out"), "tag": "t-"}) == []
