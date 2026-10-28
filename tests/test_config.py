"""Frozen calibrated values are layered between base defaults and explicit configs."""

import yaml

from amm import paths
from amm.config import load_config


def test_frozen_layer_order(tmp_path, monkeypatch):
    (tmp_path / "base.yaml").write_text(yaml.safe_dump({"frozen_policy_file": "frozen.yaml", "a": 1, "b": {"x": 1, "y": 1}}))
    (tmp_path / "frozen.yaml").write_text(yaml.safe_dump({"values": {"a": 2, "b": {"x": 2}}}))
    (tmp_path / "leaf.yaml").write_text(yaml.safe_dump({"extends": "base.yaml", "b": {"y": 3}}))
    (tmp_path / "leaf2.yaml").write_text(yaml.safe_dump({"extends": "base.yaml", "a": 9}))
    monkeypatch.setattr(paths, "CONFIGS", tmp_path)
    base = load_config(tmp_path / "base.yaml")
    assert base["a"] == 2 and base["b"] == {"x": 2, "y": 1}  # frozen overrides base defaults
    leaf = load_config(tmp_path / "leaf.yaml")
    assert leaf["a"] == 2 and leaf["b"] == {"x": 2, "y": 3}
    assert load_config(tmp_path / "leaf2.yaml")["a"] == 9  # an explicit leaf value wins
    off = load_config(tmp_path / "leaf.yaml", overrides={"frozen_policy_file": None})
    assert off["a"] == 1 and off["b"]["x"] == 1  # calibration runs from base values
    assert load_config(tmp_path / "base.yaml", overrides={"a": 5})["a"] == 5
