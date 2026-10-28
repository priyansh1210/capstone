"""Explanations that keep three different things apart:

1. Input-distribution change: do recent *covariates* (weather, observed before
   labels arrive) look different from what the active model was trained on?
   Seasonal variables always differ between a 2-week window and a full
   training year, so the reference is restricted to training rows from the
   same calendar months, and the shift is the standardized difference of
   means (z = (recent mean - reference mean) / reference SD). PSI was tried
   first but is always large for two weeks of autocorrelated weather.
2. Change in the demand relationship: given the inputs, is the model now
   systematically off? Measured by the residual bias of revealed labels.
3. Observed performance deterioration: is error actually worse than the
   model's reference error? (computed in policy.evidence)

None of these proves a cause; they are reported side by side.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SHIFT_FEATURES = ["temp_c", "humidity", "windspeed_ms", "pressure_hpa", "cloud_cover"]
Z_NOTABLE = 1.0  # recent mean more than one training SD from season-matched training data


def input_profile(X: pd.DataFrame, max_rows: int = 6000, seed: int = 0) -> pd.DataFrame:
    """Small sample of training covariates kept with each model version."""
    cols = [c for c in SHIFT_FEATURES + ["mnth"] if c in X.columns]
    Xp = X[cols]
    if len(Xp) > max_rows:
        Xp = Xp.sample(max_rows, random_state=seed)
    return Xp.reset_index(drop=True)


def input_shift(profile: pd.DataFrame | None, recent: pd.DataFrame) -> dict:
    if profile is None or len(recent) == 0:
        return {"available": False}
    months = set(recent["mnth"].dropna().astype(int)) if "mnth" in recent else set()
    ref = profile[profile["mnth"].isin(months)] if months and "mnth" in profile else profile
    if len(ref) < 100:
        return {"available": False, "reason": "no season-matched training rows"}
    scores = {}
    for f in SHIFT_FEATURES:
        if f in recent and f in ref:
            r, c = ref[f].to_numpy(float), recent[f].to_numpy(float)
            sd = np.nanstd(r)
            if sd > 0 and np.isfinite(np.nanmean(c)):
                scores[f] = round(float((np.nanmean(c) - np.nanmean(r)) / sd), 2)
    worst = max(scores, key=lambda k: abs(scores[k])) if scores else None
    return {
        "available": True,
        "z_shift": scores,
        "max_abs_z": abs(scores[worst]) if worst else None,
        "max_feature": worst,
        "notable": bool(worst and abs(scores[worst]) >= Z_NOTABLE),
        "reference": f"training rows from months {sorted(int(m) for m in months)}",
    }


def explain(perf: dict, shift: dict, bias: float | None) -> str:
    parts = []
    if perf.get("recent_signal") is not None:
        parts.append(
            f"seasonally-adjusted error {perf['recent_signal']:.3f} vs reference {perf['reference_signal']:.3f} "
            f"({perf['ratio'] - 1:+.0%}) over {perf['n']} labelled hours (MAE {perf['recent_mae']:.1f})"
        )
    if bias is not None:
        direction = "over" if bias > 0 else "under"
        parts.append(f"model {direction}-predicts total demand by {abs(bias):.0%} (relationship/level evidence)")
    if shift.get("available"):
        z = shift["z_shift"][shift["max_feature"]]
        if shift["notable"]:
            parts.append(f"inputs shifted: {shift['max_feature']} {z:+.1f} SD vs season-matched training data")
        else:
            parts.append(f"no large input shift (largest: {shift['max_feature']} {z:+.1f} SD)")
    return "; ".join(parts)
