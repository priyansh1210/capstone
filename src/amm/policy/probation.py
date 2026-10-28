"""Post-promotion observation with paired predictions.

After a promotion both the new (active) and the previous model predict every
arriving batch *before* its labels are revealed. Once labels arrive, their
errors are compared on exactly the same hours. The comparison is made in
consecutive checkpoint windows of ``window_hours`` paired hours:

* rollback if the new model's MAE is >= previous MAE * (1 + rollback_rel_margin)
  in ``consecutive_windows`` consecutive windows ("consistently worse");
* keep if ``max_windows`` windows pass without that happening.

Because the comparison is paired, a general rise in error that affects both
models (e.g. a demand shock) does not by itself cause a rollback.
"""

from __future__ import annotations

import numpy as np

from amm.metrics import scaled_error


class Probation:
    def __init__(self, new_version: str, prev_version: str, start_step: int, cfg: dict):
        pc = cfg["probation"]
        self.new, self.prev, self.start_step = new_version, prev_version, start_step
        self.window_hours = pc["window_hours"]
        self.max_windows = pc["max_windows"]
        self.margin = pc["rollback_rel_margin"]
        self.need = pc["consecutive_windows"]
        self._buf_new, self._buf_prev, self._buf_y = [], [], []
        self.windows: list[dict] = []
        self.all_new, self.all_prev, self.all_y, self.all_m, self.all_ts = [], [], [], [], []
        self.decision: str | None = None

    def add(self, y: np.ndarray, yhat_new: np.ndarray, yhat_prev: np.ndarray, months=None, ts=None) -> list[dict]:
        """Add paired outcomes; returns any completed checkpoint windows."""
        done = []
        self.all_m.extend(months if months is not None else np.ones(len(y), int))
        if ts is not None:
            self.all_ts.extend(np.asarray(ts, dtype="datetime64[ns]"))
        self.all_new.extend(yhat_new)
        self.all_prev.extend(yhat_prev)
        self.all_y.extend(y)
        for i in range(len(y)):
            if self.decision:
                break
            self._buf_y.append(y[i])
            self._buf_new.append(yhat_new[i])
            self._buf_prev.append(yhat_prev[i])
            if len(self._buf_y) >= self.window_hours:
                done.append(self._close_window())
        return done

    def _close_window(self) -> dict:
        y = np.asarray(self._buf_y)
        n, p = np.asarray(self._buf_new), np.asarray(self._buf_prev)
        mae_new, mae_prev = float(np.abs(y - n).mean()), float(np.abs(y - p).mean())
        worse = mae_new >= mae_prev * (1 + self.margin)
        w = {
            "window": len(self.windows) + 1,
            "n": int(len(y)),
            "mae_new": mae_new,
            "mae_prev": mae_prev,
            "ratio": mae_new / max(mae_prev, 1e-9),
            "new_worse": bool(worse),
            "new_better_share": float(np.mean(np.abs(y - n) < np.abs(y - p))),
        }
        self.windows.append(w)
        self._buf_y, self._buf_new, self._buf_prev = [], [], []
        tail = self.windows[-self.need:]
        if len(tail) == self.need and all(x["new_worse"] for x in tail):
            self.decision = "rollback"
        elif len(self.windows) >= self.max_windows:
            self.decision = "keep"
        return w

    def summary(self) -> dict:
        y = np.asarray(self.all_y, float)
        if len(y) == 0:
            return {"n": 0}
        n, p = np.asarray(self.all_new, float), np.asarray(self.all_prev, float)
        return {
            "n": int(len(y)),
            "mae_new": float(np.abs(y - n).mean()),
            "mae_prev": float(np.abs(y - p).mean()),
            "scaled_new": float(scaled_error(y, n).mean()),
            "scaled_prev": float(scaled_error(y, p).mean()),
            "windows": self.windows,
        }
