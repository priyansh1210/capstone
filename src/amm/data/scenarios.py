"""Replay scenarios A-D and their manifests.

A  bike_unmodified    held-out chronological source observations (2018-2024), no injected change.
                      "Unmodified", not "stationary": real demand changed a lot (COVID-19, e-bikes).
B  bike_abrupt        copy of A; from a hidden date, demand in selected working-day hours x factor.
C  bike_gradual       copy of A; the same factor ramps in linearly over a hidden interval.
D  synthetic_stationary  fully generated, fixed input distribution / relationship / noise.
(+ synthetic_abrupt   generated with a known abrupt change; used for clean detection-delay checks)

The manifest (seeds, transformation, hidden change timestamps) is for the
evaluator and UI only; it is never handed to the controller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from amm import paths
from amm.data import synthetic
from amm.data.dataset import load_hourly, split_partitions
from amm.data.features import TARGET

KIND_LABEL = {
    "source": "Source observations (Capital Bikeshare trips aggregated hourly + NOAA DCA weather)",
    "modified": "Modified observations (source data with a documented, injected demand change)",
    "generated": "Fully generated data (seeded synthetic stream)",
}


@dataclass
class Scenario:
    name: str
    kind: str  # source | modified | generated
    description: str
    train: pd.DataFrame
    calibration: pd.DataFrame
    replay: pd.DataFrame
    manifest: dict = field(default_factory=dict)

    @property
    def history(self) -> pd.DataFrame:
        return pd.concat([self.train, self.calibration], ignore_index=True)

    @property
    def kind_label(self) -> str:
        return KIND_LABEL[self.kind]

    def change_seq(self) -> int | None:
        """First replay seq affected by the injected change (evaluator only)."""
        ch = self.manifest.get("change")
        if not ch:
            return None
        ts = pd.Timestamp(ch["start"])
        after = self.replay[self.replay["ts_local"] >= ts]
        return int(after["seq"].iloc[0]) if len(after) else None


def _with_seq(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["seq"] = df["instant"].astype("int64")
    return df


def bike(cfg: dict, variant: str = "unmodified", partitions: dict | None = None, change: dict | None = None, name: str | None = None) -> Scenario:
    parts = split_partitions(load_hourly(), partitions or cfg["data"]["partitions"])
    train, cal, rep = (_with_seq(parts[k]) for k in ("train", "calibration", "replay"))
    manifest = {
        "scenario": name or f"bike_{variant}",
        "data_source": "Capital Bikeshare system data + NOAA ISD-Lite (DCA)",
        "partitions": partitions or cfg["data"]["partitions"],
        "change": None,
    }
    kind = "source"
    if variant != "unmodified":
        ch = dict(change or cfg["scenarios"][variant])
        if variant == "abrupt":
            ch.pop("end", None)
        f = synthetic.change_factor(rep, ch)
        before = rep[TARGET].to_numpy()
        rep[TARGET] = np.round(before * f).astype("int64")  # stays a non-negative integer count
        ch["type"] = variant
        ch["rows_modified"] = int((f != 1.0).sum())
        ch["target_total_before"] = int(before.sum())
        ch["target_total_after"] = int(rep[TARGET].sum())
        manifest["change"] = ch
        kind = "modified"
    desc = {
        "unmodified": "Held-out 2018-2024 hourly demand, unmodified (contains real changes such as COVID-19).",
        "abrupt": "Held-out demand with an injected abrupt increase in selected working-day hours.",
        "gradual": "Held-out demand with an injected gradual increase in selected working-day hours.",
    }[variant]
    from amm.data.fallback import is_fallback

    if is_fallback():
        kind = "generated"
        manifest["data_source"] = "GENERATED_FALLBACK (raw sources unavailable) - not Capital Bikeshare/UCI"
        desc = "GENERATED FALLBACK DATA, not real observations. " + desc
    return Scenario(manifest["scenario"], kind, desc, train, cal, rep, manifest)


def generated(cfg: dict, seed: int, variant: str = "stationary", change: dict | None = None) -> Scenario:
    sc = cfg["scenarios"]["synthetic"]
    n_tr, n_cal, n_rep = sc["days_train"], sc["days_calibration"], sc["days_replay"]
    ch = None
    if variant == "abrupt":
        ch = dict(change or sc["abrupt_change"])
        ch["start"] = str(pd.Timestamp(synthetic.START) + pd.Timedelta(days=n_tr + n_cal + ch.pop("day_offset")))
        ch["type"] = "abrupt"
    df = synthetic.generate(seed, n_tr + n_cal + n_rep, change=ch)
    day = (df["ts_local"] - df["ts_local"].iloc[0]).dt.days
    train, cal, rep = df[day < n_tr], df[(day >= n_tr) & (day < n_tr + n_cal)], df[day >= n_tr + n_cal]
    manifest = {
        "scenario": f"synthetic_{variant}",
        "data_source": "generated (amm.data.synthetic)",
        "seed": seed,
        "generator": "AR(1) weather, fixed hour profiles, negative binomial noise r=25",
        "days": {"train": n_tr, "calibration": n_cal, "replay": n_rep},
        "change": ch,
    }
    desc = "Fully generated stream; distribution, relationship and noise fixed" + (" except one injected abrupt change." if ch else ".")
    return Scenario(manifest["scenario"], "generated", desc, train.copy(), cal.copy(), rep.copy(), manifest)


EVAL_SCENARIOS = ("bike_unmodified", "bike_abrupt", "bike_gradual", "synthetic_stationary", "synthetic_abrupt")


def build(name: str, cfg: dict, seed: int | None = None) -> Scenario:
    if name.startswith("bike_"):
        return bike(cfg, name[len("bike_"):])
    if name.startswith("synthetic_"):
        return generated(cfg, seed if seed is not None else cfg["seed"], name[len("synthetic_"):])
    if name.startswith("dev_bike_"):
        variant = name[len("dev_bike_"):]
        d = cfg["dev"]
        return bike(cfg, variant, partitions=d["partitions"], change=d.get(variant), name=name)
    raise KeyError(name)


def write_manifests(cfg: dict) -> list[str]:
    """Materialise scenario streams + manifests under data/scenarios/ for inspection."""
    out = []
    for name in EVAL_SCENARIOS:
        seeds = cfg["scenarios"]["synthetic"]["seeds"][:1] if name.startswith("synthetic") else [None]
        for s in seeds:
            sc = build(name, cfg, s)
            d = paths.SCENARIOS / sc.name
            d.mkdir(parents=True, exist_ok=True)
            sc.replay.to_parquet(d / "replay.parquet", index=False)
            m = dict(sc.manifest, kind=sc.kind, kind_label=sc.kind_label, description=sc.description,
                     replay_rows=len(sc.replay), replay_range=[str(sc.replay.ts_local.min()), str(sc.replay.ts_local.max())])
            (d / "manifest.json").write_text(json.dumps(m, indent=2, default=str))
            out.append(str(d))
    return out
