from __future__ import annotations

from typing import Iterable

import numpy as np


def calculate_supt_dij(values: Iterable[float], window_size: int | None = None) -> float:
    """
    Compute the SUPT d_ij score from a numeric series.

    Logic:
    1. Optional rolling window trim
    2. Log transform with +1 shift
    3. Absolute gaps between consecutive log values
    4. d_ij = std(gaps) / mean(gaps)

    A value >= 1.0 is treated as a clutch/congestion threshold in this prototype.
    """
    array = np.asarray(list(values), dtype=float)

    array = array[np.isfinite(array)]
    if window_size is not None and len(array) > window_size:
        array = array[-window_size:]

    if len(array) < 2:
        return 0.0

    min_value = float(np.min(array))
    if min_value < 0:
        array = array - min_value

    log_data = np.log(array + 1.0)
    gaps = np.abs(np.diff(log_data))
    gaps = gaps[np.isfinite(gaps)]

    if len(gaps) == 0:
        return 0.0

    mean_gap = float(np.mean(gaps))
    std_gap = float(np.std(gaps))

    if mean_gap == 0.0:
        return 0.0

    return std_gap / mean_gap


def summarize_series(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]

    if len(array) == 0:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }