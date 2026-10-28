"""Performance monitoring of the *active* model on revealed labels.

* Rolling MAE / RMSE / scaled error and sample counts since the last rebase.
* River ADWIN fed with the *detector signal*: the scaled error
  |log1p(y) - log1p(yhat)| (capped at 3) divided by the calibration-estimated
  monthly difficulty index (metrics.SeasonalIndex). One value per revealed
  hour, in reveal order.
* ADWIN reports a change in the *mean* of the signal in either direction; we
  record the direction (estimate before vs after the cut). A detection is a
  statistical signal only; the controller separately checks whether error has
  actually worsened before acting.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from amm.metrics import scaled_error


def make_adwin(delta: float, clock: int):
    from river import drift

    return drift.ADWIN(delta=delta, clock=clock)


def make_detector(kind: str, delta: float, clock: int, params: dict | None = None):
    """ADWIN (default), Page-Hinkley (increase-only) or KSWIN from River."""
    from river import drift

    params = params or {}
    if kind == "adwin":
        return make_adwin(delta, clock)
    if kind == "page_hinkley":
        return drift.PageHinkley(mode="up", **params)
    if kind == "kswin":
        return drift.KSWIN(seed=7, **params)
    raise ValueError(f"unknown detector {kind}")


@dataclass
class Detection:
    step: int
    seq: int
    est_before: float
    est_after: float
    width_after: int

    @property
    def increase(self) -> bool:
        return self.est_after > self.est_before


class Monitor:
    def __init__(self, delta: float = 0.002, clock: int = 24, rolling_hours: int = 168, keep_hours: int = 2000, warm_hours: int = 672,
                 detector: str = "adwin", detector_params: dict | None = None):
        self.delta, self.clock = delta, clock
        self.kind, self.detector_params = detector, detector_params or {}
        self.rolling_hours = rolling_hours
        self.keep = keep_hours
        self.warm_hours = warm_hours
        self.reset(step=0)

    def reset(self, step: int, warm=None) -> None:
        """Rebase after a model change: errors of the old model must not count
        against the new one, and improvement must not look like drift.

        ``warm``: detector-signal values of the new model on its *reference*
        window (calibration / validation / paired probation). They are fed to
        ADWIN first, so live errors are tested against the evidence on which
        the model was accepted. Without this, a model that is already worse
        than its reference on day one looks "stable" to ADWIN. Warm values do
        not enter the rolling live metrics, and detections inside them are ignored.
        """
        self.detector = make_detector(self.kind, self.delta, self.clock, self.detector_params)
        self.warm_n = 0
        self._hist = deque(maxlen=1000)  # recent signal incl. warm values, for change direction
        if warm is not None and self.warm_hours > 0:
            for x in np.asarray(warm, float)[-self.warm_hours:]:
                self.detector.update(float(x))
                self._hist.append(float(x))
                self.warm_n += 1
        self.since_step = step
        self.n = 0
        self._abs = deque(maxlen=self.keep)
        self._sq = deque(maxlen=self.keep)
        self._sc = deque(maxlen=self.keep)
        self._sig = deque(maxlen=self.keep)
        self._y = deque(maxlen=self.keep)
        self._p = deque(maxlen=self.keep)
        self._batch_sig = deque(maxlen=400)  # mean detector signal per revealed batch (day)
        self.detections: list[Detection] = []

    def update(self, step: int, seq: np.ndarray, y: np.ndarray, yhat: np.ndarray, signal: np.ndarray) -> list[Detection]:
        """Callers pass only hours that count as model errors (outage hours are
        excluded upstream; they are still scored in the evaluation)."""
        if len(y) == 0:
            return []
        err = np.abs(y - yhat)
        sc = scaled_error(y, yhat)
        new = []
        for i in range(len(y)):
            x = float(signal[i])
            if self.kind == "adwin":
                before = self.detector.estimation
                self.detector.update(x)
                if self.detector.drift_detected:
                    new.append(Detection(step, int(seq[i]), float(before), float(self.detector.estimation), int(self.detector.width)))
            else:
                self._hist.append(x)
                self.detector.update(x)
                if self.detector.drift_detected:
                    h = np.fromiter(self._hist, float)
                    after = float(h[-168:].mean())
                    before = float(h[:-168].mean()) if len(h) > 168 else after
                    new.append(Detection(step, int(seq[i]), before, after, len(h)))
        self.detections.extend(new)
        self._abs.extend(err)
        self._sq.extend(err**2)
        self._sc.extend(sc)
        self._sig.extend(signal)
        self._y.extend(y)
        self._p.extend(yhat)
        self._batch_sig.append(float(np.mean(signal)))
        self.n += len(y)
        return new

    def batch_median(self, n_batches: int) -> tuple[float | None, int]:
        b = list(self._batch_sig)[-n_batches:]
        return (float(np.median(b)) if b else None), len(b)

    def window(self, hours: int) -> dict:
        k = min(hours, len(self._abs))
        if k == 0:
            return {"n": 0, "mae": None, "rmse": None, "scaled": None, "signal": None, "bias": None}

        def tail(d):
            return np.fromiter(d, float)[-k:]

        y, p = tail(self._y), tail(self._p)
        return {
            "n": int(k),
            "mae": float(tail(self._abs).mean()),
            "rmse": float(np.sqrt(tail(self._sq).mean())),
            "scaled": float(tail(self._sc).mean()),
            "signal": float(tail(self._sig).mean()),
            "bias": float(p.sum() / max(y.sum(), 1.0) - 1.0),
        }

    def rolling(self) -> dict:
        return self.window(self.rolling_hours)

    @property
    def adwin_width(self) -> int:
        return int(getattr(self.detector, "width", 0) or 0)
