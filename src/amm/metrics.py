"""Error metrics and the scaled error signal fed to the drift detector."""

from __future__ import annotations

import numpy as np

SCALED_ERROR_CAP = 3.0


def scaled_error(y_true, y_pred) -> np.ndarray:
    """Absolute error on the log1p scale, capped at 3.

    Demand ranges from ~0 at night to >2,000 trips/h, so raw absolute errors
    grow with the demand level (and with the season and the year). The log
    scale makes a 20 % miss at 1,000 trips comparable to a 20 % miss at 100,
    which keeps the detector's input consistently scaled across seasons and
    years. The cap bounds the influence of outage hours (system closed).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return np.minimum(np.abs(np.log1p(y_true) - np.log1p(np.clip(y_pred, 0, None))), SCALED_ERROR_CAP)


class SeasonalIndex:
    """Monthly difficulty index for the scaled error.

    Even a well-fitted model has ~2x higher scaled error in Dec/Jan (tiny night
    counts) than in summer. Comparing a 2-week window against a single
    reference number would therefore raise seasonal "deterioration". The
    index is estimated once from the *initial model's calibration-period*
    errors (circular 3-month smoothing, mean 1) and the detector signal is
    ``scaled_error / index[month]``. Assumption (documented): the seasonal
    difficulty pattern is stable across years - checked on calibration data.
    """

    def __init__(self, factors=None):
        self.factors = np.ones(13) if factors is None else np.asarray(factors, float)

    @classmethod
    def fit(cls, errors, months) -> "SeasonalIndex":
        errors, months = np.asarray(errors, float), np.asarray(months, int)
        raw = np.array([errors[months == m].mean() if np.any(months == m) else np.nan for m in range(1, 13)])
        raw = np.where(np.isnan(raw), np.nanmean(raw), raw)
        smooth = (np.roll(raw, 1) + raw + np.roll(raw, -1)) / 3.0
        smooth = smooth / smooth.mean()
        return cls(np.concatenate([[1.0], smooth]))  # index 0 unused

    def signal(self, scaled, months) -> np.ndarray:
        return np.asarray(scaled, float) / self.factors[np.asarray(months, int)]

    def as_dict(self) -> dict:
        return {m: round(float(self.factors[m]), 3) for m in range(1, 13)}


def daily_median(signal, ts) -> float:
    """Median over calendar days of the daily mean signal (robust reference:
    one blizzard or outage day cannot dominate it)."""
    signal = np.asarray(signal, float)
    if len(signal) == 0:
        return float("nan")
    days = np.asarray(ts, dtype="datetime64[D]")
    _, inv = np.unique(days, return_inverse=True)
    sums = np.bincount(inv, weights=signal)
    cnts = np.bincount(inv)
    return float(np.median(sums / cnts))


def months_of(ts) -> np.ndarray:
    return np.asarray(ts, dtype="datetime64[M]").astype(int) % 12 + 1


def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(np.asarray(y_true, float) - np.asarray(y_pred, float))))


def rmse(y_true, y_pred) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true, float) - np.asarray(y_pred, float)) ** 2)))


def summarize(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    if len(y_true) == 0:
        return {"n": 0, "mae": None, "rmse": None, "scaled": None, "bias": None}
    return {
        "n": int(len(y_true)),
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "scaled": float(scaled_error(y_true, y_pred).mean()),
        # relative bias of totals: >0 means the model over-predicts demand
        "bias": float(y_pred.sum() / max(y_true.sum(), 1.0) - 1.0),
    }
