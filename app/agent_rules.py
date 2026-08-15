from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.gradient_policy import classify_gradient_decision


@dataclass(frozen=True)
class AgentDecision:
    risk_state: str
    confidence: float

    should_execute: bool
    allow_new_entries: bool
    max_position_multiplier: float

    execution_mode: str
    suggested_action: str
    reason: str

    channel_desync: bool
    baseline_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_state": self.risk_state,
            "confidence": self.confidence,
            "should_execute": self.should_execute,
            "allow_new_entries": self.allow_new_entries,
            "max_position_multiplier": self.max_position_multiplier,
            "execution_mode": self.execution_mode,
            "suggested_action": self.suggested_action,
            "reason": self.reason,
            "channel_desync": self.channel_desync,
            "baseline_action": self.baseline_action,
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def _confidence_for_state(state: str) -> float:
    state = state.upper()

    if state == "HIGH_STRESS":
        return 0.92
    if state == "CAUTION":
        return 0.84
    if state == "EARLY_CAUTION":
        return 0.74
    if state == "RECOVERY":
        return 0.82
    if state == "NORMAL":
        return 0.90

    return 0.60


def classify_agent_state(
    *,
    current_payload: dict[str, Any],
    previous_risk_state: str | None = None,
) -> AgentDecision:
    dij_data = current_payload.get("d_ij", {}) or {}
    alert_data = current_payload.get("alert", {}) or {}

    composite_dij = _safe_float(
        dij_data.get("composite", current_payload.get("composite_dij"))
    )
    tx_dij = _safe_float(
        dij_data.get("tx_count", current_payload.get("tx_dij")),
        composite_dij,
    )
    gas_dij = _safe_float(
        dij_data.get("gas", current_payload.get("gas_dij"))
    )
    base_fee_dij = _safe_float(
        dij_data.get("base_fee", current_payload.get("base_fee_dij"))
    )

    alert_active = _safe_bool(
        alert_data.get("is_active", current_payload.get("alert_active"))
    )

    decision = classify_gradient_decision(
        composite_dij=composite_dij,
        tx_dij=tx_dij,
        gas_dij=gas_dij,
        base_fee_dij=base_fee_dij,
        alert_active=alert_active,
        previous_state=previous_risk_state,
    )

    return AgentDecision(
        risk_state=decision.risk_state,
        confidence=_confidence_for_state(decision.risk_state),
        should_execute=decision.should_execute,
        allow_new_entries=decision.allow_new_entries,
        max_position_multiplier=decision.max_position_multiplier,
        execution_mode=decision.execution_mode,
        suggested_action=decision.action,
        reason=decision.reason,
        channel_desync=decision.channel_desync,
        baseline_action="Execute normally without regime filter.",
    )
