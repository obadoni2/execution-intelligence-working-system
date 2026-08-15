from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Dict, List

from equities.spy_channels import build_channels, load_spy_rows


ALPHA = 0.01
TAIL_N = 50

INPUT_CSV = Path("equities/data/spy_sample.csv")
OUTPUT_CSV = Path("equities/data/spy_probe_output.csv")


def mean(values: List[float]) -> float:
    clean = [v for v in values if math.isfinite(v)]

    if not clean:
        return 0.0

    return sum(clean) / len(clean)


def std(values: List[float]) -> float:
    clean = [v for v in values if math.isfinite(v)]

    if len(clean) < 2:
        return 0.0

    return statistics.pstdev(clean)


def compute_dij(
    values: List[float],
    tail_n: int = TAIL_N,
    alpha: float = ALPHA,
) -> float:
    clean = []

    for v in values:
        try:
            fv = float(v)

            if math.isfinite(fv):
                clean.append(fv)

        except Exception:
            continue

    if len(clean) < 5:
        return 0.0

    window = clean[-tail_n:] if len(clean) >= tail_n else clean
    baseline = clean[:-tail_n] if len(clean) > tail_n else clean

    mu = mean(baseline)
    sigma = std(baseline)

    if sigma <= 1e-9:
        sigma = max(abs(mu) * alpha, 1e-9)

    latest = window[-1]

    z = abs(latest - mu) / sigma

    trend = 0.0

    if len(window) >= 2:
        trend = abs(window[-1] - window[0]) / sigma

    return round(float((0.75 * z) + (0.25 * trend)), 6)


def classify(dij: float) -> str:
    if dij >= 1.0:
        return "CLUTCH"

    return "COHERENCE"


def run_probe() -> None:
    rows = load_spy_rows(INPUT_CSV)

    if not rows:
        raise FileNotFoundError(
            f"No SPY input data found at {INPUT_CSV}"
        )

    channels = build_channels(rows)

    spread_series: List[float] = []
    depth_series: List[float] = []
    qtu_series: List[float] = []

    output: List[Dict[str, object]] = []

    for row in channels:
        spread_series.append(float(row["spread"]))
        depth_series.append(float(row["depth"]))
        qtu_series.append(float(row["quote_trade_ratio"]))

        spread_dij = compute_dij(spread_series)
        depth_dij = compute_dij(depth_series)
        qtu_dij = compute_dij(qtu_series)

        composite_dij = round(
            (spread_dij + depth_dij + qtu_dij) / 3.0,
            6,
        )

        divergence = round(
            max(spread_dij, depth_dij, qtu_dij)
            - min(spread_dij, depth_dij, qtu_dij),
            6,
        )

        output.append(
            {
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "spread": row["spread"],
                "depth": row["depth"],
                "quote_trade_ratio": row["quote_trade_ratio"],
                "spread_dij": spread_dij,
                "depth_dij": depth_dij,
                "quote_trade_ratio_dij": qtu_dij,
                "composite_dij": composite_dij,
                "divergence": divergence,
                "regime": classify(composite_dij),
                "production_connected": False,
            }
        )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(output[0].keys()),
        )

        writer.writeheader()
        writer.writerows(output)

    print(
        f"Wrote {len(output)} SPY probe rows to {OUTPUT_CSV}"
    )


if __name__ == "__main__":
    run_probe()
