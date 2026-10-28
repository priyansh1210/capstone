"""Has prediction error actually worsened? (separate from the ADWIN signal)"""

from __future__ import annotations

from amm.monitoring.monitor import Monitor


def deterioration(monitor: Monitor, reference_signal: float, cfg: dict) -> dict:
    """Compare the active model's recent detector signal (seasonally adjusted
    scaled error) with its reference value.

    Statistic: the median over the last ``recent_hours / 24`` revealed batches
    (days) of the daily mean signal, so a single anomalous day cannot trigger
    retraining ("sustained"). The reference is the same daily-median statistic
    on the model's reference window. Deteriorated iff the recent median is at
    least ``reference * (1 + rel_margin)`` *and* ``reference + abs_margin``.
    Requires at least half the window to be available.
    """
    dc = cfg["policy"]["deterioration"]
    w = monitor.window(dc["recent_hours"])
    n_batches = max(1, dc["recent_hours"] // 24)
    med, nb = monitor.batch_median(n_batches)
    w["signal"] = med if nb >= max(1, n_batches // 2) else None
    min_n = dc["recent_hours"] // 2
    out = {
        "n": w["n"],
        "recent_signal": w["signal"],
        "recent_scaled": w["scaled"],
        "recent_mae": w["mae"],
        "bias": w["bias"],
        "reference_signal": reference_signal,
        "rel_margin": dc["rel_margin"],
        "abs_margin": dc["abs_margin"],
        "min_n": min_n,
    }
    if w["n"] < min_n or w["signal"] is None:
        out.update(deteriorated=False, ratio=None, reason=f"only {w['n']} labelled hours since rebase (< {min_n})")
        return out
    ratio = w["signal"] / max(reference_signal, 1e-9)
    threshold = max(reference_signal * (1 + dc["rel_margin"]), reference_signal + dc["abs_margin"])
    out.update(ratio=ratio, threshold=threshold, deteriorated=bool(w["signal"] >= threshold))
    out["reason"] = (
        f"recent seasonally-adjusted error {w['signal']:.3f} {'>=' if out['deteriorated'] else '<'} threshold {threshold:.3f}"
    )
    return out
