from __future__ import annotations

import csv
from collections import deque
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query

from app.api.calibration import CALIBRATION_VERSION, calibration_sha

router = APIRouter(prefix="/v1", tags=["Decision Outcomes"])

OUTCOMES_PATH = Path("data/decision_outcomes.csv")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def load_recent(limit: int) -> List[Dict[str, Any]]:
    if not OUTCOMES_PATH.exists():
        return []

    with OUTCOMES_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = deque(reader, maxlen=limit)

    return list(rows)


def normalize(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp_utc": row.get("timestamp"),
        "chain": row.get("chain"),
        "block_number": row.get("block_number"),
        "risk_state": row.get("risk_state"),
        "action": row.get("action"),
        "should_execute": safe_bool(row.get("should_execute")),
        "confidence": safe_float(row.get("confidence")),
        "composite_d_ij": safe_float(row.get("composite_dij")),
        "gas_d_ij": safe_float(row.get("gas_dij")),
        "base_fee_d_ij": safe_float(row.get("base_fee_dij")),
        "horizon_rows": int(float(row.get("horizon_rows", 0))),
        "future_bad": safe_bool(row.get("future_bad")),
        "future_bad_count": int(float(row.get("future_bad_count", 0))),
        "correct": safe_bool(row.get("correct")),
        "baseline_risk_exposure": safe_float(row.get("baseline_risk_exposure")),
        "agent_risk_exposure": safe_float(row.get("agent_risk_exposure")),
        "avoided_risk_exposure": safe_float(row.get("avoided_risk_exposure")),
        "reason": row.get("reason"),
    }


@router.get("/decision-outcomes")
def decision_outcomes(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    rows = [normalize(r) for r in load_recent(limit)]

    count = len(rows)
    correct_count = sum(1 for r in rows if r["correct"])
    future_bad_count = sum(1 for r in rows if r["future_bad"])
    pause_count = sum(1 for r in rows if r["action"] == "PAUSE")
    total_avoided = sum(r["avoided_risk_exposure"] for r in rows)

    accuracy = correct_count / count if count else 0.0

    return {
        "schema_version": "supt.decision_outcomes.v1",
        "source_file": str(OUTCOMES_PATH),
        "limit": limit,
        "count": count,
        "summary": {
            "correct_count": correct_count,
            "accuracy": accuracy,
            "future_bad_count": future_bad_count,
            "pause_count": pause_count,
            "total_avoided_risk_exposure": total_avoided,
        },
        "calibration": {
            "version": CALIBRATION_VERSION,
            "receipt_sha": calibration_sha(),
        },
        "outcomes": rows,
    }
