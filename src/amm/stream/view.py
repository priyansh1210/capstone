"""ControllerView: the only window the controller has onto the world.

The simulator *pushes* data into the view: covariates once they are observed
(at prediction time) and labels once their reveal step has arrived. The view
holds no reference to the simulator, the full dataframe or any scenario
manifest, so the controller cannot read future targets or the hidden change
point even by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Labelled:
    X: pd.DataFrame
    y: np.ndarray
    seq: np.ndarray
    ts: np.ndarray  # datetime64[ns]

    def __len__(self) -> int:
        return len(self.y)

    def take(self, idx) -> "Labelled":
        return Labelled(self.X.iloc[idx].reset_index(drop=True), self.y[idx], self.seq[idx], self.ts[idx])


class ControllerView:
    def __init__(self, features: list[str]):
        self.features = list(features)
        self.now = 0
        self._lab_parts: list[tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]] = []
        self._lab_cache: Labelled | None = None
        self._obs_parts: list[tuple[pd.DataFrame, np.ndarray]] = []
        self._max_label_seq = -1

    # ---- write side: called by the simulator only -------------------------
    def _set_now(self, step: int) -> None:
        self.now = step

    def _push_labels(self, X: pd.DataFrame, y: np.ndarray, seq: np.ndarray, ts: np.ndarray) -> None:
        if len(seq) == 0:
            return
        if seq.min() <= self._max_label_seq:
            raise ValueError("labels must be revealed in sequence order exactly once")
        self._lab_parts.append((X[self.features].reset_index(drop=True), np.asarray(y, float), seq, ts))
        self._max_label_seq = int(seq.max())
        self._lab_cache = None

    def _push_covariates(self, X: pd.DataFrame, ts: np.ndarray) -> None:
        self._obs_parts.append((X[self.features].reset_index(drop=True), ts))
        # only recent covariates are needed: keep roughly the last 4,096 rows
        total, keep = 0, 0
        for part, _ in reversed(self._obs_parts):
            total += len(part)
            keep += 1
            if total >= 4096:
                break
        self._obs_parts = self._obs_parts[-keep:]

    # ---- read side ---------------------------------------------------------
    def labelled(self) -> Labelled:
        if self._lab_cache is None:
            if not self._lab_parts:
                self._lab_cache = Labelled(pd.DataFrame(columns=self.features), np.array([]), np.array([], int), np.array([], "datetime64[ns]"))
            else:
                X = pd.concat([p[0] for p in self._lab_parts], ignore_index=True)
                y = np.concatenate([p[1] for p in self._lab_parts])
                seq = np.concatenate([p[2] for p in self._lab_parts])
                ts = np.concatenate([p[3] for p in self._lab_parts])
                self._lab_parts = [(X, y, seq, ts)]
                self._lab_cache = Labelled(X, y, seq, ts)
        return self._lab_cache

    @property
    def last_labelled_seq(self) -> int:
        return self._max_label_seq

    def recent_covariates(self, n_rows: int) -> pd.DataFrame:
        if not self._obs_parts:
            return pd.DataFrame(columns=self.features)
        parts, rows = [], 0
        for part, _ in reversed(self._obs_parts):
            parts.append(part)
            rows += len(part)
            if rows >= n_rows:
                break
        X = pd.concat(parts[::-1], ignore_index=True)
        return X.tail(n_rows).reset_index(drop=True)
