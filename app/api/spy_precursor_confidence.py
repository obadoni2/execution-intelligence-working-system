from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query


router = APIRouter(prefix="/v1", tags=["SPY Precursor Confidence"])

PROBE_PATH = Path("equities/data/spy_probe_output.csv")
THRESHOLD = 1.0

CHANNELS = {
    "spread": "spread_dij",
    "depth": "depth_dij",
    "quote_trade_ratio": "quote_trade_ratio_dij",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def load_rows() -> List[Dict[str, Any]]:
    if not PROBE_PATH.exists():
        return []

    with PROBE_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def crosses(prev: float, curr: float, threshold: float = THRESHOLD) -> bool:
    return prev < threshold <= curr


def confidence_label(score: float) -> str:
    if score >= 0.85:
        return "EXTREME"
    if score >= 0.70:
        return "HIGH"
    if score >= 0.50:
        return "MEDIUM"
    return "LOW"


@router.get("/spy-precursor-confidence")
def spy_precursor_confidence(
    horizon_rows: int = Query(default=30, ge=1, le=300),
) -> Dict[str, Any]:
    rows = load_rows()
    n = len(rows)

    if n < horizon_rows + 2:
        return {
            "schema_version": "supt.spy_precursor_confidence.v1",
            "error": "not_enough_rows",
            "total_rows": n,
        }

    # Baseline probability from random row.
    baseline_hits = 0
    baseline_eval = 0

    for i in range(0, n - horizon_rows):
        future = rows[i + 1 : i + 1 + horizon_rows]
        hit = any(safe_float(r.get("composite_dij")) >= THRESHOLD for r in future)
        baseline_eval += 1
        baseline_hits += 1 if hit else 0

    baseline_prob = baseline_hits / baseline_eval if baseline_eval else 0.0

    channel_results = {}

    for channel, col in CHANNELS.items():
        crosses_total = 0
        future_hits = 0
        lead_rows = []

        for i in range(1, n - horizon_rows):
            prev_val = safe_float(rows[i - 1].get(col))
            curr_val = safe_float(rows[i].get(col))

            if not crosses(prev_val, curr_val):
                continue

            crosses_total += 1

            future = rows[i + 1 : i + 1 + horizon_rows]
            future_cross_indices = [
                j + 1
                for j, r in enumerate(future)
                if safe_float(r.get("composite_dij")) >= THRESHOLD
            ]

            if future_cross_indices:
                future_hits += 1
                lead_rows.append(future_cross_indices[0])

        conditional_prob = future_hits / crosses_total if crosses_total else 0.0
        lift_vs_baseline = conditional_prob / baseline_prob if baseline_prob else 0.0

        avg_lead = sum(lead_rows) / len(lead_rows) if lead_rows else 0.0
        max_lead = max(lead_rows) if lead_rows else 0

        # Confidence score combines conditional probability, baseline lift, and lead reach.
        prob_component = conditional_prob
        lift_component = min(lift_vs_baseline / 3.0, 1.0)
        lead_component = min(max_lead / horizon_rows, 1.0)

        score = round(
            (0.55 * prob_component)
            + (0.30 * lift_component)
            + (0.15 * lead_component),
            6,
        )

        channel_results[channel] = {
            "channel_cross_count": crosses_total,
            "future_composite_stress_hits": future_hits,
            "conditional_probability": conditional_prob,
            "baseline_probability": baseline_prob,
            "lift_vs_baseline": lift_vs_baseline,
            "average_rows_to_composite": avg_lead,
            "max_rows_to_composite": max_lead,
            "precursor_confidence_score": score,
            "confidence_label": confidence_label(score),
        }

    ranked = sorted(
        channel_results.items(),
        key=lambda kv: kv[1]["precursor_confidence_score"],
        reverse=True,
    )

    return {
        "schema_version": "supt.spy_precursor_confidence.v1",
        "source_file": str(PROBE_PATH),
        "threshold": THRESHOLD,
        "horizon_rows": horizon_rows,
        "baseline_probability": baseline_prob,
        "channels": channel_results,
        "ranked_channels": [
            {"channel": name, **data}
            for name, data in ranked
        ],
        "interpretation": {
            "purpose": "Scores how operationally meaningful a channel precursor is.",
            "score_inputs": [
                "conditional probability",
                "lift versus baseline",
                "maximum lead reach",
            ],
        },
    }
