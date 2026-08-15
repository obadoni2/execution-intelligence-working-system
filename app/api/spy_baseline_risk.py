from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query


router = APIRouter(prefix="/v1", tags=["SPY Baseline Risk"])

PROBE_PATH = Path("equities/data/spy_probe_output.csv")
THRESHOLD = 1.0


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


@router.get("/spy-baseline-risk")
def spy_baseline_risk(
    horizon_rows: int = Query(default=30, ge=1, le=300),
) -> Dict[str, Any]:
    rows = load_rows()
    n = len(rows)

    if n < horizon_rows + 1:
        return {
            "schema_version": "supt.spy_baseline_risk.v1",
            "error": "not_enough_rows",
            "total_rows": n,
        }

    future_stress = 0
    evaluated = 0

    for i in range(0, n - horizon_rows):
        future = rows[i + 1 : i + 1 + horizon_rows]
        hit = any(
            safe_float(r.get("composite_dij")) >= THRESHOLD
            for r in future
        )

        evaluated += 1

        if hit:
            future_stress += 1

    baseline_probability = future_stress / evaluated if evaluated else 0.0

    return {
        "schema_version": "supt.spy_baseline_risk.v1",
        "source_file": str(PROBE_PATH),
        "threshold": THRESHOLD,
        "horizon_rows": horizon_rows,
        "total_rows": n,
        "evaluated_rows": evaluated,
        "future_stress_hits": future_stress,
        "p_composite_stress_within_horizon_random_row": baseline_probability,
        "interpretation": {
            "purpose": "Baseline probability of composite stress within the forward horizon from any random row.",
            "why_it_matters": "This lets conditional precursor probabilities be compared against normal background stress probability.",
        },
    }
