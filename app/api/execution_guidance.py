from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.api.decision_api import decision

router = APIRouter(prefix="/v1", tags=["Execution Guidance"])


@router.get("/execution-guidance")
def execution_guidance() -> Dict[str, Any]:
    payload = decision()

    recommendation = payload.get("recommendation", {})
    regime = payload.get("regime", {})

    action = recommendation.get("action", "UNKNOWN")
    viability = regime.get("viability_score")
    bad_rate = recommendation.get("expected_bad_rate")

    operator_guidance = {
        "EXECUTE_FULL": "Execution conditions appear stable. Normal execution is acceptable.",
        "SELECTIVE_EXECUTE": "Execution conditions show mild instability. Prefer selective or lower urgency execution.",
        "REDUCE_SIZE": "Execution stress increasing. Reduce position size and avoid aggressive routing.",
        "PAUSE": "Pause non-urgent execution until conditions stabilize.",
        "RESUME_GRADUALLY": "Conditions recovering. Resume execution gradually and monitor stability.",
    }.get(action, "Monitor execution conditions carefully.")

    return {
        "schema_version": "supt.execution_guidance.v1",
        "can_execute_now": bool(recommendation.get("should_execute", False)),
        "recommended_action": action,
        "operator_guidance": operator_guidance,
        "risk_state": regime.get("label"),
        "raw_monitor_regime": regime.get("raw_monitor_regime"),
        "viability_score": viability,
        "expected_bad_rate": bad_rate,
        "max_position_multiplier": recommendation.get("max_position_multiplier"),
        "reason": recommendation.get("primary_reason"),
        "confidence": recommendation.get("confidence"),
    }
