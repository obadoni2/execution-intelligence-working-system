from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GradientDecision:
    risk_state: str
    execution_mode: str
    should_execute: bool
    allow_new_entries: bool
    max_position_multiplier: float
    action: str
    reason: str
    channel_desync: bool


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def classify_gradient_decision(
    *,
    composite_dij: float,
    tx_dij: float,
    gas_dij: float,
    base_fee_dij: float,
    alert_active: bool,
    previous_state: str | None = None,
) -> GradientDecision:
    """
    Gradient execution policy.

    Gas-channel divergence = early warning.
    Composite d_ij = confirmation.
    Proximity-to-threshold = action intensity.
    """

    gas_early = _env_float("GAS_EARLY_CAUTION_THRESHOLD", 0.90)
    gas_stress = _env_float("GAS_STRESS_THRESHOLD", 1.00)
    gas_extreme = _env_float("GAS_EXTREME_THRESHOLD", 1.20)

    composite_caution = _env_float("COMPOSITE_CAUTION_THRESHOLD", 0.85)
    composite_stress = _env_float("COMPOSITE_STRESS_THRESHOLD", 1.00)
    composite_relaxed = _env_float("COMPOSITE_RELAXED_THRESHOLD", 0.85)

    base_fee_caution = _env_float("BASE_FEE_CAUTION_THRESHOLD", 0.85)
    base_fee_stress = _env_float("BASE_FEE_STRESS_THRESHOLD", 1.00)

    normal_mult = _env_float("NORMAL_MULTIPLIER", 1.00)
    early_mult = _env_float("EARLY_CAUTION_MULTIPLIER", 0.75)
    caution_mult = _env_float("CAUTION_MULTIPLIER", 0.35)
    recovery_mult = _env_float("RECOVERY_MULTIPLIER", 0.50)

    channel_max = max(tx_dij, gas_dij, base_fee_dij)
    channel_min = min(tx_dij, gas_dij, base_fee_dij)

    channel_desync = channel_max >= gas_stress and channel_min < composite_stress

    previous_state = (previous_state or "").upper()

    # Confirmed stress: composite confirms and gas/alert supports it.
    if composite_dij >= composite_stress and (gas_dij >= gas_stress or alert_active):
        return GradientDecision(
            risk_state="HIGH_STRESS",
            execution_mode="PAUSE",
            should_execute=False,
            allow_new_entries=False,
            max_position_multiplier=0.0,
            action="Pause non-urgent execution.",
            reason=(
                f"Confirmed stress: composite={composite_dij:.4f}, "
                f"gas={gas_dij:.4f}, base_fee={base_fee_dij:.4f}, "
                f"alert_active={alert_active}."
            ),
            channel_desync=channel_desync,
        )

    # Extreme gas can trigger high stress even before full composite confirmation.
    if gas_dij >= gas_extreme and composite_dij >= composite_caution:
        return GradientDecision(
            risk_state="HIGH_STRESS",
            execution_mode="PAUSE",
            should_execute=False,
            allow_new_entries=False,
            max_position_multiplier=0.0,
            action="Pause non-urgent execution because gas channel is extremely elevated.",
            reason=(
                f"Gas extreme lead: gas={gas_dij:.4f}, "
                f"composite={composite_dij:.4f}."
            ),
            channel_desync=True,
        )

    # Strong caution: gas/base fee stress or composite close to stress.
    if (
        composite_dij >= composite_stress
        or gas_dij >= gas_stress
        or base_fee_dij >= base_fee_stress
        or channel_desync
    ):
        return GradientDecision(
            risk_state="CAUTION",
            execution_mode="REDUCE_SIZE",
            should_execute=True,
            allow_new_entries=False,
            max_position_multiplier=caution_mult,
            action="Reduce size and delay non-urgent/aggressive execution.",
            reason=(
                f"Caution: composite={composite_dij:.4f}, "
                f"gas={gas_dij:.4f}, base_fee={base_fee_dij:.4f}, "
                f"channel_desync={channel_desync}."
            ),
            channel_desync=channel_desync,
        )

    # Recovery: stress recently happened but channels are now clearing.
    if previous_state in {"HIGH_STRESS", "CAUTION", "EARLY_CAUTION"}:
        if (
            composite_dij < composite_stress
            and gas_dij < gas_stress
            and base_fee_dij < base_fee_stress
            and not alert_active
        ):
            return GradientDecision(
                risk_state="RECOVERY",
                execution_mode="RESUME_GRADUALLY",
                should_execute=True,
                allow_new_entries=True,
                max_position_multiplier=recovery_mult,
                action="Resume gradually after stress clears.",
                reason=(
                    f"Recovery: composite={composite_dij:.4f}, "
                    f"gas={gas_dij:.4f}, base_fee={base_fee_dij:.4f}."
                ),
                channel_desync=False,
            )

    # Early caution: gas is leading while composite is still below stress.
    if (
        gas_dij >= gas_early
        or composite_dij >= composite_caution
        or base_fee_dij >= base_fee_caution
    ):
        return GradientDecision(
            risk_state="EARLY_CAUTION",
            execution_mode="SELECTIVE_EXECUTE",
            should_execute=True,
            allow_new_entries=True,
            max_position_multiplier=early_mult,
            action="Selective execution: avoid large entries and monitor for confirmation.",
            reason=(
                f"Near-threshold / early warning: composite={composite_dij:.4f}, "
                f"gas={gas_dij:.4f}, base_fee={base_fee_dij:.4f}."
            ),
            channel_desync=channel_desync,
        )

    # Fully relaxed coherence.
    if (
        composite_dij < composite_relaxed
        and gas_dij < gas_early
        and base_fee_dij < base_fee_caution
        and not alert_active
    ):
        return GradientDecision(
            risk_state="NORMAL",
            execution_mode="EXECUTE_FULL",
            should_execute=True,
            allow_new_entries=True,
            max_position_multiplier=normal_mult,
            action="Normal execution allowed.",
            reason=(
                f"Relaxed coherence: composite={composite_dij:.4f}, "
                f"gas={gas_dij:.4f}, base_fee={base_fee_dij:.4f}."
            ),
            channel_desync=False,
        )

    return GradientDecision(
        risk_state="NORMAL",
        execution_mode="EXECUTE_FULL",
        should_execute=True,
        allow_new_entries=True,
        max_position_multiplier=normal_mult,
        action="Normal execution allowed.",
        reason=(
            f"Default normal: composite={composite_dij:.4f}, "
            f"gas={gas_dij:.4f}, base_fee={base_fee_dij:.4f}."
        ),
        channel_desync=channel_desync,
    )
