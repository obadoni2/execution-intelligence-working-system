from __future__ import annotations

import csv
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.api.calibration import (
    CALIBRATION_VERSION,
    calibration_sha,
    get_calibration,
    get_state_calibration,
)

router = APIRouter(prefix="/v1", tags=["SUPT Decision Intelligence"])

AGENT_DECISIONS_PATH = Path("data/agent_decisions.csv")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def read_latest_agent_decision() -> Optional[Dict[str, Any]]:
    if not AGENT_DECISIONS_PATH.exists():
        return None

    with AGENT_DECISIONS_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = deque(reader, maxlen=1)

    if not rows:
        return None

    return dict(rows[0])


@router.get("/calibration")
def calibration() -> Dict[str, Any]:
    return get_calibration()


@router.get("/calibration/{version}")
def calibration_by_version(version: str) -> Dict[str, Any]:
    payload = get_calibration()
    payload["requested_version"] = version
    return payload


@router.get("/decision")
def decision() -> Dict[str, Any]:
    live = read_latest_agent_decision()

    if live is None:
        state = "NORMAL"
        state_cal = get_state_calibration(state)

        return {
            "schema_version": "supt.decision.v1",
            "timestamp_utc": now_utc(),
            "status": "no_live_agent_data",
            "block_number": None,
            "regime": {
                "label": state,
                "severity_ordinal": state_cal["ordinal"],
                "composite_d_ij": None,
                "gas_d_ij": None,
                "base_fee_d_ij": None,
                "viability_score": state_cal["viability_score"],
                "viability_basis": "empirical_calibration_n506",
            },
            "recommendation": {
                "action": state_cal["execution_mode"],
                "primary_reason": "NO_AGENT_DATA_AVAILABLE",
                "expected_bad_rate": state_cal["future_bad_rate"],
                "calibration_n": state_cal["n"],
                "confidence": "fallback",
            },
            "calibration": {
                "version": CALIBRATION_VERSION,
                "receipt_sha": calibration_sha(),
                "validation_blocks": [19000149, 25015827],
                "validation_n": 506,
            },
        }

    state = str(live.get("risk_state") or "NORMAL").upper()
    state_cal = get_state_calibration(state)

    composite_dij = safe_float(live.get("composite_dij"))
    gas_dij = safe_float(live.get("gas_dij"))
    base_fee_dij = safe_float(live.get("base_fee_dij"))
    tx_dij = safe_float(live.get("tx_dij"))

    alert_active = safe_bool(live.get("alert_active"))
    channel_desync = safe_bool(live.get("channel_desync"))

    leading_channel = None
    if gas_dij > base_fee_dij:
        leading_channel = "gas"
    elif base_fee_dij > gas_dij:
        leading_channel = "base_fee"

    interpretation = "quiescent"
    interpretation_confidence = "high"

    if channel_desync and leading_channel == "gas":
        interpretation = "mempool_buildup"
    elif channel_desync and leading_channel == "base_fee":
        interpretation = "settlement_pressure"
        interpretation_confidence = "moderate"
    elif channel_desync:
        interpretation = "mixed"
        interpretation_confidence = "moderate"

    blocks_to_clutch = None
    if state in {"EARLY_CAUTION", "CAUTION"} and composite_dij < 1.0 and channel_desync:
        blocks_to_clutch = 18

    blocks_to_normal = None
    if state in {"HIGH_STRESS", "RECOVERY"}:
        blocks_to_normal = None

    return {
        "schema_version": "supt.decision.v1",
        "timestamp_utc": now_utc(),
        "agent_timestamp_utc": live.get("timestamp"),
        "chain": live.get("chain", "eth"),
        "block_number": safe_int(live.get("latest_block")),
        "monitor_status": live.get("monitor_status"),
        "regime": {
            "label": state,
            "raw_monitor_regime": live.get("regime"),
            "severity_ordinal": state_cal["ordinal"],
            "composite_d_ij": composite_dij,
            "tx_d_ij": tx_dij,
            "gas_d_ij": gas_dij,
            "base_fee_d_ij": base_fee_dij,
            "alert_active": alert_active,
            "channel_desync": channel_desync,
            "viability_score": state_cal["viability_score"],
            "viability_basis": "empirical_calibration_n506",
        },
        "recommendation": {
            "action": live.get("execution_mode") or state_cal["execution_mode"],
            "suggested_action": live.get("suggested_action"),
            "primary_reason": live.get("reason"),
            "expected_bad_rate": state_cal["future_bad_rate"],
            "calibration_n": state_cal["n"],
            "confidence": live.get("confidence", "calibrated"),
            "should_execute": safe_bool(live.get("should_execute")),
            "allow_new_entries": safe_bool(live.get("allow_new_entries")),
            "max_position_multiplier": safe_float(live.get("max_position_multiplier")),
        },
        "risk_accounting": {
            "execution_risk_score": safe_float(live.get("execution_risk_score")),
            "baseline_risk_exposure": safe_float(live.get("baseline_risk_exposure")),
            "agent_risk_exposure": safe_float(live.get("agent_risk_exposure")),
            "avoided_risk_exposure": safe_float(live.get("avoided_risk_exposure")),
            "baseline_notional": safe_float(live.get("baseline_notional")),
            "agent_notional": safe_float(live.get("agent_notional")),
            "avoided_notional": safe_float(live.get("avoided_notional")),
        },
        "forecast": {
            "blocks_to_clutch": blocks_to_clutch,
            "blocks_to_normal": blocks_to_normal,
            "lead_basis": "transition_events_n8_median",
            "divergence": {
                "leading_channel": leading_channel,
                "lead_blocks": 18 if channel_desync else None,
                "interpretation": interpretation,
                "interpretation_confidence": interpretation_confidence,
            },
        },
        "calibration": {
            "version": CALIBRATION_VERSION,
            "receipt_sha": calibration_sha(),
            "validation_blocks": [19000149, 25015827],
            "validation_n": 506,
        },
        "freshness": {
            "staleness_blocks": 1,
            "max_staleness_sla": 2,
            "rolling_window": 150,
            "rpc_provider": "ethereum-rpc.publicnode.com",
            "source_file": str(AGENT_DECISIONS_PATH),
        },
    }
