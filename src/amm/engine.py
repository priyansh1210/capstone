"""Session: one policy replaying one scenario. Shared by the CLI and dashboard.

Step order (see stream.simulator): reveal labels -> score + monitor ->
decide -> predict next batch -> record. Each step is one SQLite transaction
and is guarded by a non-blocking lock, so a concurrent call (e.g. a Streamlit
rerun) cannot execute a step twice.
"""

from __future__ import annotations

import copy
import threading
import time
import uuid
from pathlib import Path

import joblib
import numpy as np

from amm import paths
from amm.data.features import FEATURES, TARGET
from amm.data.quality import outage_mask
from amm.data.scenarios import Scenario
from amm.metrics import SeasonalIndex, daily_median, months_of, scaled_error, summarize
from amm.models.candidates import make_model
from amm.models.registry import ModelVersion, Registry
from amm.monitoring import diagnostics
from amm.policy.controller import Controller
from amm.storage.store import Store
from amm.stream.simulator import ReplaySimulator


class DuplicateStepError(RuntimeError):
    pass


def train_initial(scenario: Scenario, cfg: dict) -> tuple:
    """Fit the initial model on the training partition only; its reference
    error is measured on the (later) calibration partition."""
    ic = cfg["initial_model"]
    tr = scenario.train
    if ic.get("window_days"):
        tr = tr[tr["ts_local"] > tr["ts_local"].max() - np.timedelta64(int(ic["window_days"]), "D")]
    tr = tr[~outage_mask(tr[TARGET].to_numpy())]
    t0 = time.perf_counter()
    model = make_model(ic["name"], seed=cfg["seed"]).fit(tr[FEATURES], tr[TARGET])
    secs = time.perf_counter() - t0
    cal = scenario.calibration
    s = summarize(cal[TARGET], model.predict(cal[FEATURES]))
    v = ModelVersion(
        version="v001",
        model_name=ic["name"],
        window_days=ic.get("window_days"),
        status="active",
        train_start=str(tr["ts_local"].min()),
        train_end=str(tr["ts_local"].max()),
        train_end_seq=int(scenario.train["seq"].max()),
        n_train=len(tr),
        val_start=str(cal["ts_local"].min()),
        val_end=str(cal["ts_local"].max()),
        val_end_seq=int(cal["seq"].max()),
        n_val=len(cal),
        val_mae=s["mae"],
        val_rmse=s["rmse"],
        val_scaled=s["scaled"],
        reference_mae=s["mae"],
        reference_scaled=s["scaled"],
        reference_source="calibration partition",
        train_seconds=secs,
        notes="initial model (identical for every policy)",
    )
    cal_scaled = scaled_error(cal[TARGET].to_numpy(float), model.predict(cal[FEATURES]))
    cal_months = months_of(cal["ts_local"].to_numpy("datetime64[ns]"))
    index = SeasonalIndex.fit(cal_scaled, cal_months) if cfg["monitor"].get("seasonal_index", True) else SeasonalIndex()
    keep = ~outage_mask(cal[TARGET].to_numpy())
    warm = index.signal(cal_scaled, cal_months)[keep]
    v.reference_signal = daily_median(warm, cal["ts_local"].to_numpy("datetime64[ns]")[keep])
    return model, v, diagnostics.input_profile(tr[FEATURES]), warm, index


class Session:
    def __init__(
        self,
        scenario: Scenario,
        policy: str,
        cfg: dict,
        store: Store,
        run_id: str | None = None,
        initial=None,
        artifact_root: Path | None = None,
        notes: str = "",
    ):
        self.cfg = cfg
        self.policy = policy
        self.scenario_name = scenario.name
        self.scenario_kind = scenario.kind
        self.run_id = run_id or f"{policy}-{scenario.name}-{uuid.uuid4().hex[:6]}"
        self.store = store
        st = cfg["stream"]
        self.sim = ReplaySimulator(
            scenario.history, scenario.replay, FEATURES, TARGET, st["label_delay_batches"], st.get("batch_by", "day"), st.get("batch_rows", 24)
        )
        model, v, profile, warm, index = initial if initial is not None else train_initial(scenario, cfg)
        model, v = copy.deepcopy(model), copy.deepcopy(v)  # each policy owns its copy
        persist = cfg.get("storage", {}).get("persist_artifacts", True)
        root = artifact_root or (paths.ARTIFACTS / "runs")
        registry = Registry(root / self.run_id / "models", persist=persist)
        registry._counter = 1
        registry.activate_initial(v, model, step=0)
        self.controller = Controller(
            policy, cfg, self.sim.view, registry, store, self.run_id, cfg["seed"], {v.version: profile}, {v.version: warm}, index
        )
        self.seasonal_index = index
        self.wall_seconds = 0.0
        store.create_run(self.run_id, policy, scenario.name, scenario.kind, cfg["seed"], cfg, self.sim.total_steps, notes)
        store.upsert_version(self.run_id, v.record())
        store.conn.commit()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ run
    @property
    def finished(self) -> bool:
        return self.sim.finished

    @property
    def t(self) -> int:
        return self.sim.t

    def step(self) -> bool:
        """Advance one replay step. Returns False if finished or busy."""
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self.sim.finished:
                return False
            t0 = time.perf_counter()
            t = self.sim.t
            if self.store.last_step(self.run_id) >= t:
                raise DuplicateStepError(f"step {t} of {self.run_id} already recorded")
            c = self.controller
            with self.store.tx():
                c.now_ts = self.sim.batch_start_ts(t)
                lb = self.sim.begin_step()
                if lb is not None:
                    c.on_labels(t, lb)
                if t < self.sim.n_batches:
                    c.decide(t)
                    cb = self.sim.covariates()
                    c.predict(t, cb, self.sim.label_reveal_step(cb.batch))
                c.record_step(t)
                self.store.set_run(self.run_id, last_step=t)
                if t + 1 >= self.sim.total_steps:
                    self.store.set_run(self.run_id, status="finished")
            self.sim.end_step()
            self.wall_seconds += time.perf_counter() - t0
            return True
        finally:
            self._lock.release()

    def run(self, max_steps: int | None = None, progress_every: int = 0) -> None:
        n = 0
        while not self.finished and (max_steps is None or n < max_steps):
            self.step()
            n += 1
            if progress_every and self.t % progress_every == 0:
                c = self.controller
                print(f"  [{self.run_id}] step {self.t}/{self.sim.total_steps} state={c.state.value} cycles={c.cycle} active={c.registry.active_id}")

    # -------------------------------------------------------- fault / demo
    def inject_demand_change(self, factor: float, hours, workingday_only=True, label="demo change"):
        ch = self.sim.inject_change(factor, hours, workingday_only, label)
        return ch

    def operator_request(self) -> bool:
        with self.store.tx():
            return self.controller.operator_request(self.sim.t)

    def inject_weak_candidates(self):
        with self.store.tx():
            self.controller.inject_weak_candidates(self.sim.t)

    def force_activate_weak(self) -> bool:
        with self.store.tx():
            return self.controller.force_activate_weak(self.sim.t)

    # ---------------------------------------------------------- checkpoint
    def __getstate__(self):
        d = self.__dict__.copy()
        d["store"] = None
        d["_lock"] = None
        d["controller"] = copy.copy(self.controller)
        d["controller"].store = None
        return d

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        joblib.dump(self, tmp, compress=3)
        tmp.replace(path)

    @staticmethod
    def load(path: Path, store: Store) -> "Session":
        s: Session = joblib.load(path)
        s.store = store
        s.controller.store = store
        s._lock = threading.Lock()
        if store.last_step(s.run_id) >= s.sim.t:
            # DB is ahead of the checkpoint: drop the newer rows, then the
            # deterministic replay re-creates them exactly once.
            store.rewind(s.run_id, s.sim.t)
            with store.tx():
                for v in s.controller.registry.versions.values():
                    store.upsert_version(s.run_id, v.record())
                n = len(s.controller.events)
                store.conn.execute("DELETE FROM decisions WHERE run_id=? AND event_id>?", (s.run_id, n))
        return s
