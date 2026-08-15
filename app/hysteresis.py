from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HysteresisResult:
    alert_active: bool
    event: str


def apply_hysteresis(
    *,
    value: float,
    previous_alert_active: bool,
    enter_threshold: float = 1.0,
    exit_threshold: float = 0.85,
) -> HysteresisResult:
    """
    Enter alert when value >= enter_threshold.
    Exit alert only when value <= exit_threshold.

    This prevents flapping around the 1.0 threshold.
    """
    if not previous_alert_active and value >= enter_threshold:
        return HysteresisResult(alert_active=True, event="ENTER_ALERT")

    if previous_alert_active and value <= exit_threshold:
        return HysteresisResult(alert_active=False, event="EXIT_ALERT")

    if previous_alert_active:
        return HysteresisResult(alert_active=True, event="HOLD_ALERT")

    return HysteresisResult(alert_active=False, event="NO_ALERT")
