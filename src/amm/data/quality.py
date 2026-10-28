"""Training-data quality rules that only use already-revealed labels."""

from __future__ import annotations

import numpy as np

OUTAGE_MIN_RUN = 6


def outage_mask(y, min_run: int = OUTAGE_MIN_RUN) -> np.ndarray:
    """True for hours inside a run of >= ``min_run`` consecutive zero-trip hours.

    Such runs are system closures (blizzards, hurricanes), not demand. Training
    on them taught models that "January is ~0" after the 2016 blizzard, so they
    are excluded from *fitting*. They are still predicted and scored.
    """
    z = np.asarray(y) == 0
    mask = np.zeros(len(z), dtype=bool)
    if not z.any():
        return mask
    # run-length encode zeros
    edges = np.flatnonzero(np.diff(np.concatenate(([0], z.astype(np.int8), [0]))))
    for start, end in zip(edges[::2], edges[1::2]):
        if end - start >= min_run:
            mask[start:end] = True
    return mask
