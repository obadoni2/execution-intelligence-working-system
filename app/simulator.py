from __future__ import annotations

from typing import Any

import numpy as np


def _generate_tx_count(step: int, rng: np.random.Generator) -> int:
    """
    Simulated ETH-like transaction count pattern:
    - calm zone
    - rising pressure
    - congestion burst
    - cool down
    """
    phase = step % 120

    if phase < 55:
        mean = 175 + 0.5 * phase
        std = 18
    elif phase < 85:
        mean = 215 + 2.2 * (phase - 55)
        std = 35
    elif phase < 105:
        mean = 320 + 4.0 * (phase - 85)
        std = 85
    else:
        mean = 220 - 1.5 * (phase - 105)
        std = 30

    value = int(rng.normal(mean, std))
    return max(value, 0)


def initialize_simulation(window_size: int) -> dict[str, Any]:
    rng = np.random.default_rng(2026)

    tx_counts: list[int] = []
    for i in range(window_size):
        tx_counts.append(_generate_tx_count(i, rng))

    return {
        "step": window_size,
        "latest_block": 19_000_000 + window_size - 1,
        "tx_counts": tx_counts,
    }


def advance_simulation(state: dict[str, Any], window_size: int) -> dict[str, Any]:
    rng = np.random.default_rng(2026 + int(state["step"]))
    next_tx_count = _generate_tx_count(int(state["step"]), rng)

    tx_counts = list(state["tx_counts"])
    tx_counts.append(next_tx_count)
    tx_counts = tx_counts[-window_size:]

    return {
        "step": int(state["step"]) + 1,
        "latest_block": int(state["latest_block"]) + 1,
        "tx_counts": tx_counts,
    } 