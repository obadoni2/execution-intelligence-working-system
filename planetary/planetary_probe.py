from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Any, List


IN = Path("planetary/data/planetary_series.csv")
OUT = Path("planetary/data/planetary_probe_output.csv")

ALPHA = 0.01
TAIL_N = 50


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def compute_dij(values: List[float]) -> float:
    clean = [float(v) for v in values if math.isfinite(float(v))]

    if len(clean) < 5:
        return 0.0

    window = clean[-TAIL_N:] if len(clean) >= TAIL_N else clean
    baseline = clean[:-TAIL_N] if len(clean) > TAIL_N else clean

    mu = mean(baseline)
    sigma = std(baseline)

    if sigma <= 1e-9:
        sigma = max(abs(mu) * ALPHA, 1e-9)

    latest = window[-1]
    z = abs(latest - mu) / sigma

    trend = 0.0
    if len(window) >= 2:
        trend = abs(window[-1] - window[0]) / sigma

    return round((0.75 * z) + (0.25 * trend), 6)


def regime(dij: float) -> str:
    if dij < 0.5:
        return "DEEP_LOCK"
    if dij < 1.0:
        return "COHERENCE"
    if dij < 2.0:
        return "CLUTCH"
    if dij < 3.61:
        return "SUB_FLOOR"
    return "VACUUM"


def main() -> None:
    if not IN.exists():
        raise FileNotFoundError("Run planetary_ingest.py first.")

    with IN.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    a_series = []
    b_series = []
    output = []

    for row in rows:
        a_series.append(safe_float(row["planetary_a"]))
        b_series.append(safe_float(row["planetary_b"]))

        a_dij = compute_dij(a_series)
        b_dij = compute_dij(b_series)

        output.append(
            {
                "date": row["date"],
                "planetary_a": row["planetary_a"],
                "planetary_b": row["planetary_b"],
                "planetary_a_dij": a_dij,
                "planetary_b_dij": b_dij,
                "planetary_a_regime": regime(a_dij),
                "planetary_b_regime": regime(b_dij),
                "read_only": True,
                "production_decision_connected": False,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

    print(f"Wrote {len(output)} planetary probe rows to {OUT}")
    print(output[-1])


if __name__ == "__main__":
    main()
