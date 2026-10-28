"""YAML configuration with single inheritance (``extends:``) and deep merge.

Merge order (later wins):
  base chain -> frozen calibrated values (configs/frozen_policy.yaml, written by
  `amm calibrate`) -> the leaf config file (if it extends another) -> overrides.
For base.yaml itself the frozen values override its defaults, which are marked
"(calibrated)". Setting ``frozen_policy_file: null`` (in a file or override)
disables the frozen layer, e.g. during calibration.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from amm import paths


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _chain(path: Path) -> list[dict]:
    raw = yaml.safe_load(path.read_text()) or {}
    parent = raw.pop("extends", None)
    return (_chain(path.parent / parent) if parent else []) + [raw]


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    if path:
        path = Path(path)
        if not path.is_absolute() and not path.exists():
            path = paths.ROOT / path
    else:
        path = paths.CONFIGS / "base.yaml"
    layers = _chain(path)
    overrides = overrides or {}
    base_layers, leaf = (layers, {}) if len(layers) == 1 else (layers[:-1], layers[-1])
    cfg: dict = {}
    for layer in base_layers:
        cfg = deep_merge(cfg, layer)
    name = deep_merge(deep_merge(cfg, leaf), overrides).get("frozen_policy_file")
    if name and (paths.CONFIGS / name).exists():
        frozen = yaml.safe_load((paths.CONFIGS / name).read_text()) or {}
        cfg = deep_merge(cfg, frozen.get("values", {}))
    return deep_merge(deep_merge(cfg, leaf), overrides)
