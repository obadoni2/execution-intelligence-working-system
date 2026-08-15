from __future__ import annotations

import csv
import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query

from app.api.calibration import CALIBRATION_VERSION, calibration_sha

router = APIRouter(prefix="/v1", tags=["Decision History"])

AGENT_DECISIONS_PATH = Path("data/agent_decisions.csv")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def decision_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_recent_rows(limit: int) -> List[Dict[str, Any]]:
    if not AGENT_DECISIONS_PATH.exists():
        return []

    with AGENT_DECISIONS_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = deque(reader, maxlen=limit)

    return list(rows)


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    risk_state = str(row.get("risk_state") or "UNKNOWN").upper()
    action = str(row.get("execution_mode") or "UNKNOWN").upper()

    item = {
        "timestamp_utc": row.get("timestamp"),
        "chain": row.get("chain", "eth"),
        "block_number": safe_int(row.get("latest_block")),
        "monitor_status": row.get("monitor_status"),
        "raw_monitor_regime": row.get("regime"),
        "risk_state": risk_state,
        "recommended_action": action,
        "should_execute": safe_bool(row.get("should_execute")),
        "allow_new_entries": safe_bool(row.get("allow_new_entries")),
        "max_position_multiplier": safe_float(row.get("max_position_multiplier")),
        "confidence": safe_float(row.get("confidence")),
        "composite_d_ij": safe_float(row.get("composite_dij")),
        "tx_d_ij": safe_float(row.get("tx_dij")),
        "gas_d_ij": safe_float(row.get("gas_dij")),
        "base_fee_d_ij": safe_float(row.get("base_fee_dij")),
        "alert_active": safe_bool(row.get("alert_active")),
        "channel_desync": safe_bool(row.get("channel_desync")),
        "suggested_action": row.get("suggested_action"),
        "reason": row.get("reason"),
        "risk_accounting": {
            "execution_risk_score": safe_float(row.get("execution_risk_score")),
            "baseline_risk_exposure": safe_float(row.get("baseline_risk_exposure")),
            "agent_risk_exposure": safe_float(row.get("agent_risk_exposure")),
            "avoided_risk_exposure": safe_float(row.get("avoided_risk_exposure")),
            "baseline_notional": safe_float(row.get("baseline_notional")),
            "agent_notional": safe_float(row.get("agent_notional")),
            "avoided_notional": safe_float(row.get("avoided_notional")),
        },
        "calibration": {
            "version": CALIBRATION_VERSION,
            "receipt_sha": calibration_sha(),
        },
    }

    item["decision_hash"] = decision_hash(item)
    return item


@router.get("/decision-history")
def decision_history(
    limit: int = Query(default=50, ge=1, le=500),
) -> Dict[str, Any]:
    rows = load_recent_rows(limit)
    decisions = [normalize_row(row) for row in rows]

    pause_count = sum(1 for d in decisions if d["recommended_action"] == "PAUSE")
    reduce_count = sum(1 for d in decisions if d["recommended_action"] == "REDUCE_SIZE")
    selective_count = sum(1 for d in decisions if d["recommended_action"] == "SELECTIVE_EXECUTE")
    full_count = sum(1 for d in decisions if d["recommended_action"] == "EXECUTE_FULL")
    resume_count = sum(1 for d in decisions if d["recommended_action"] == "RESUME_GRADUALLY")

    total_avoided_risk = sum(
        d["risk_accounting"]["avoided_risk_exposure"] for d in decisions
    )

    return {
        "schema_version": "supt.decision_history.v1",
        "source_file": str(AGENT_DECISIONS_PATH),
        "limit": limit,
        "count": len(decisions),
        "summary": {
            "pause_count": pause_count,
            "reduce_size_count": reduce_count,
            "selective_execute_count": selective_count,
            "execute_full_count": full_count,
            "resume_gradually_count": resume_count,
            "total_avoided_risk_exposure": total_avoided_risk,
        },
        "calibration": {
            "version": CALIBRATION_VERSION,
            "receipt_sha": calibration_sha(),
        },
        "decisions": decisions,
    }
