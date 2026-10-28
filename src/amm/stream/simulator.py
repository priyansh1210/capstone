"""Chronological replay with delayed labels.

Clock (one *step* per replay batch, a batch is one local calendar day by default):

1. ``begin_step``  - labels of batch ``t - delay`` become visible (pushed to the view)
2. the controller decides (may retrain / promote / roll back)
3. ``covariates``  - inputs of batch ``t`` are observed and predicted; each hourly
   prediction is made at the start of its hour with weather lagged by 1 h
4. ``end_step``    - t += 1

After the last batch, ``drain`` steps reveal the outstanding labels so every
prediction is scored. The simulator keeps the full frame privately; the
controller only ever sees what was pushed into its ControllerView.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from amm.stream.view import ControllerView


@dataclass
class LabelBatch:
    batch: int
    seq: np.ndarray
    ts: np.ndarray
    y: np.ndarray


@dataclass
class CovariateBatch:
    batch: int
    X: pd.DataFrame
    seq: np.ndarray
    ts: np.ndarray


@dataclass
class InjectedChange:
    """A change introduced through the simulator at run time (demo). Hidden from the controller."""

    from_batch: int
    factor: float
    hours: list[int]
    workingday_only: bool
    label: str
    rows_affected: int = 0
    extra: dict = field(default_factory=dict)


class ReplaySimulator:
    def __init__(
        self,
        history: pd.DataFrame,
        stream: pd.DataFrame,
        features: list[str],
        target: str,
        delay_batches: int = 1,
        batch_by: str = "day",
        batch_rows: int = 24,
    ):
        if delay_batches < 1:
            raise ValueError("label delay must be at least one batch")
        if len(history) and len(stream) and history["seq"].max() >= stream["seq"].min():
            raise ValueError("history must precede the replay stream")
        self.features = list(features)
        self.target = target
        self.delay = int(delay_batches)
        s = stream.sort_values("seq").reset_index(drop=True)
        self._X = s[self.features].copy()
        self._y = s[target].to_numpy(dtype=float).copy()
        self._seq = s["seq"].to_numpy()
        self._ts = s["ts_local"].to_numpy(dtype="datetime64[ns]")
        self._workingday = s["workingday"].to_numpy() if "workingday" in s else np.zeros(len(s), int)
        self._hr = s["hr"].to_numpy() if "hr" in s else np.zeros(len(s), int)
        if batch_by == "day":
            day = pd.to_datetime(self._ts).normalize()
            codes = (day - day[0]).days.to_numpy()
        elif batch_by == "rows":
            codes = np.arange(len(s)) // batch_rows
        else:
            raise ValueError(batch_by)
        uniq, starts = np.unique(codes, return_index=True)
        self._starts = np.append(starts, len(s))
        self.n_batches = len(uniq)
        self.t = 0
        self.changes: list[InjectedChange] = []
        self.view = ControllerView(self.features)
        h = history.sort_values("seq")
        self.view._push_labels(
            h[self.features], h[target].to_numpy(float), h["seq"].to_numpy(), h["ts_local"].to_numpy("datetime64[ns]")
        )

    # ------------------------------------------------------------------ info
    @property
    def total_steps(self) -> int:
        return self.n_batches + self.delay  # trailing drain steps reveal the last labels

    @property
    def finished(self) -> bool:
        return self.t >= self.total_steps

    def batch_slice(self, b: int) -> slice:
        return slice(self._starts[b], self._starts[b + 1])

    def batch_start_ts(self, b: int):
        b = min(b, self.n_batches - 1)
        return pd.Timestamp(self._ts[self._starts[b]])

    # ------------------------------------------------------------------ clock
    def begin_step(self) -> LabelBatch | None:
        self.view._set_now(self.t)
        r = self.t - self.delay
        if 0 <= r < self.n_batches:
            sl = self.batch_slice(r)
            lb = LabelBatch(r, self._seq[sl], self._ts[sl], self._y[sl].copy())
            self.view._push_labels(self._X.iloc[sl], lb.y, lb.seq, lb.ts)
            return lb
        return None

    def covariates(self) -> CovariateBatch | None:
        if self.t >= self.n_batches:
            return None
        sl = self.batch_slice(self.t)
        X = self._X.iloc[sl].reset_index(drop=True)
        self.view._push_covariates(X, self._ts[sl])
        return CovariateBatch(self.t, X, self._seq[sl], self._ts[sl])

    def end_step(self) -> None:
        self.t += 1

    def label_reveal_step(self, batch: int) -> int:
        return batch + self.delay

    # --------------------------------------------------------------- demo
    def inject_change(self, factor: float, hours, workingday_only: bool = True, label: str = "demo change") -> InjectedChange:
        """Multiply future demand (batches not yet predicted) in the given hours.
        Targets stay non-negative integers. Recorded for the evaluator/UI only."""
        start = self._starts[min(self.t, self.n_batches)]
        mask = np.zeros(len(self._y), bool)
        mask[start:] = True
        mask &= np.isin(self._hr, list(hours))
        if workingday_only:
            mask &= self._workingday == 1
        self._y[mask] = np.round(self._y[mask] * factor)
        ch = InjectedChange(self.t, factor, sorted(hours), workingday_only, label, int(mask.sum()))
        self.changes.append(ch)
        return ch
