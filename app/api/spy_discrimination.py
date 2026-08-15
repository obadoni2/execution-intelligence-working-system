from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter


router = APIRouter(prefix="/v1", tags=["SPY Discrimination"])

RECEIPTS_PATH = Path("equities/data/spy_outcomes.csv")


def load_receipts() -> List[Dict[str, Any]]:
    if not RECEIPTS_PATH.exists():
        return []

    with RECEIPTS_PATH.open("r", encoding="utf-8") as f:
        clean_lines = [line for line in f if not line.startswith("#")]

    return list(csv.DictReader(clean_lines))


@router.get("/spy-discrimination")
def spy_discrimination() -> Dict[str, Any]:
    rows = load_receipts()

    total = len(rows)
    bad = [r for r in rows if r.get("is_bad") == "TRUE"]

    baseline_bad_rate = len(bad) / total if total else 0.0

    state_counts = Counter(r.get("decision_state", "UNKNOWN") for r in rows)
    state_bad = Counter(r.get("decision_state", "UNKNOWN") for r in bad)

    state_metrics = {}
    for state, count in state_counts.items():
        bad_count = state_bad[state]
        bad_rate = bad_count / count if count else 0.0
        state_metrics[state] = {
            "total": count,
            "bad": bad_count,
            "clean": count - bad_count,
            "bad_rate": bad_rate,
            "lift_vs_baseline": bad_rate / baseline_bad_rate if baseline_bad_rate else 0.0,
            "delta_vs_baseline": bad_rate - baseline_bad_rate,
        }

    high = state_metrics.get("HIGH_STRESS", {})
    high_bad_rate = float(high.get("bad_rate", 0.0))

    non_high_rows = [r for r in rows if r.get("decision_state") != "HIGH_STRESS"]
    non_high_bad = [r for r in non_high_rows if r.get("is_bad") == "TRUE"]
    non_high_bad_rate = len(non_high_bad) / len(non_high_rows) if non_high_rows else 0.0

    discrimination_gap = high_bad_rate - non_high_bad_rate

    return {
        "schema_version": "supt.spy_discrimination.v1",
        "source_file": str(RECEIPTS_PATH),
        "total_receipts": total,
        "baseline_bad_rate": baseline_bad_rate,
        "high_stress_bad_rate": high_bad_rate,
        "non_high_stress_bad_rate": non_high_bad_rate,
        "high_stress_lift_vs_baseline": high_bad_rate / baseline_bad_rate if baseline_bad_rate else 0.0,
        "discrimination_gap": discrimination_gap,
        "state_metrics": state_metrics,
        "interpretation": {
            "verdict": (
                "discriminating"
                if discrimination_gap > 0.15
                else "weak_or_unproven"
            ),
            "note": "HIGH_STRESS should show materially higher future-bad rate than non-HIGH_STRESS states.",
        },
    }
