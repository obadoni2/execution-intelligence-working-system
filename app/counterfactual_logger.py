from __future__ import annotations

import csv
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from app.hysteresis import apply_hysteresis
from app.gradient_policy import classify_gradient_decision


FIELDS = [
    "timestamp",
    "chain",
    "latest_block",
    "block_hash",

    "monitor_status",
    "regime",
    "composite_dij",
    "tx_dij",
    "gas_dij",
    "base_fee_dij",
    "raw_alert_active",

    "hysteresis_alert_active",
    "hysteresis_event",
    "episode_id",

    "agent_risk_state",
    "agent_execution_mode",
    "agent_should_execute",
    "agent_notional",
    "agent_action",

    "baseline_execution_mode",
    "baseline_should_execute",
    "baseline_notional",
    "baseline_action",

    "avoided_notional",

    "execution_risk_score",
    "gas_pressure_proxy",
    "slippage_pressure_proxy",
    "confirmation_delay_proxy",
    "failed_tx_risk_proxy",

    "baseline_risk_exposure",
    "agent_risk_exposure",
    "avoided_risk_exposure",
]


@dataclass(frozen=True)
class AgentDecision:
    risk_state: str
    execution_mode: str
    should_execute: bool
    max_position_multiplier: float
    action: str


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
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


def _read_existing(path: str | Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        return pd.DataFrame(columns=FIELDS)

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=FIELDS)


def _append_row(path: str | Path, row: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)

        if not exists:
            writer.writeheader()

        writer.writerow({field: row.get(field, "") for field in FIELDS})


def _extract_monitor_values(payload: dict[str, Any]) -> dict[str, Any]:
    dij = payload.get("d_ij", {}) or {}
    alert = payload.get("alert", {}) or {}

    composite = _safe_float(dij.get("composite", payload.get("composite_dij")))
    tx = _safe_float(dij.get("tx_count", payload.get("tx_dij")), composite)
    gas = _safe_float(dij.get("gas", payload.get("gas_dij")))
    base_fee = _safe_float(dij.get("base_fee", payload.get("base_fee_dij")))

    return {
        "chain": payload.get("chain", "ethereum"),
        "latest_block": payload.get("latest_block", ""),
        "block_hash": payload.get("latest_block_hash", payload.get("block_hash", "")),
        "monitor_status": payload.get("status", "unknown"),
        "regime": payload.get("regime", ""),
        "composite_dij": composite,
        "tx_dij": tx,
        "gas_dij": gas,
        "base_fee_dij": base_fee,
        "raw_alert_active": _safe_bool(alert.get("is_active", payload.get("alert_active"))),
    }


def _classify_decision(
    *,
    composite_dij: float,
    tx_dij: float,
    gas_dij: float,
    base_fee_dij: float,
    alert_active: bool,
    previous_state: str | None,
) -> AgentDecision:
    """
    Deterministic decision layer.

    NORMAL      -> execute full
    CAUTION     -> reduce size
    HIGH_STRESS -> pause
    RECOVERY    -> resume gradually
    """
    channel_desync = max(tx_dij, gas_dij, base_fee_dij) >= 1.0 and min(tx_dij, gas_dij, base_fee_dij) < 1.0

    if composite_dij >= 1.0 and (gas_dij >= 1.0 or alert_active):
        return AgentDecision(
            risk_state="HIGH_STRESS",
            execution_mode="PAUSE",
            should_execute=False,
            max_position_multiplier=0.0,
            action="Pause new entries and delay non-urgent execution.",
        )

    if composite_dij >= 1.0 or channel_desync:
        return AgentDecision(
            risk_state="CAUTION",
            execution_mode="REDUCE_SIZE",
            should_execute=True,
            max_position_multiplier=0.25,
            action="Reduce execution size and avoid aggressive entries.",
        )

    if previous_state in {"HIGH_STRESS", "CAUTION"} and composite_dij < 1.0 and not alert_active:
        return AgentDecision(
            risk_state="RECOVERY",
            execution_mode="RESUME_GRADUALLY",
            should_execute=True,
            max_position_multiplier=0.50,
            action="Resume gradually after stress clears.",
        )

    if composite_dij >= 0.85 or gas_dij >= 0.85 or base_fee_dij >= 0.85:
        return AgentDecision(
            risk_state="CAUTION",
            execution_mode="REDUCE_SIZE",
            should_execute=True,
            max_position_multiplier=0.50,
            action="Proceed carefully; network is near stress threshold.",
        )

    return AgentDecision(
        risk_state="NORMAL",
        execution_mode="EXECUTE_FULL",
        should_execute=True,
        max_position_multiplier=1.0,
        action="Normal execution allowed.",
    )


def _risk_metrics(
    *,
    composite_dij: float,
    tx_dij: float,
    gas_dij: float,
    base_fee_dij: float,
    alert_active: bool,
) -> dict[str, float]:
    execution_risk_score = (
        0.40 * composite_dij
        + 0.25 * gas_dij
        + 0.20 * base_fee_dij
        + 0.15 * tx_dij
    )

    if alert_active:
        execution_risk_score += 0.25

    gas_pressure_proxy = max(gas_dij, base_fee_dij)
    slippage_pressure_proxy = max(composite_dij, tx_dij, gas_dij)
    confirmation_delay_proxy = max(composite_dij, base_fee_dij)

    failed_tx_risk_proxy = 0.0
    failed_tx_risk_proxy += max(0.0, composite_dij - 0.85) * 0.30
    failed_tx_risk_proxy += max(0.0, gas_dij - 0.85) * 0.35
    failed_tx_risk_proxy += max(0.0, base_fee_dij - 0.85) * 0.20

    if alert_active:
        failed_tx_risk_proxy += 0.25

    failed_tx_risk_proxy = max(0.0, min(1.0, failed_tx_risk_proxy))

    return {
        "execution_risk_score": execution_risk_score,
        "gas_pressure_proxy": gas_pressure_proxy,
        "slippage_pressure_proxy": slippage_pressure_proxy,
        "confirmation_delay_proxy": confirmation_delay_proxy,
        "failed_tx_risk_proxy": failed_tx_risk_proxy,
    }


class CounterfactualLogger:
    def __init__(
        self,
        *,
        monitor_api_url: str,
        output_path: str,
        baseline_notional: float,
        request_timeout_seconds: int,
        log_same_block: bool,
        enter_threshold: float,
        exit_threshold: float,
    ) -> None:
        self.monitor_api_url = monitor_api_url
        self.output_path = output_path
        self.baseline_notional = baseline_notional
        self.request_timeout_seconds = request_timeout_seconds
        self.log_same_block = log_same_block
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold

    def fetch_current(self) -> dict[str, Any]:
        response = requests.get(self.monitor_api_url, timeout=self.request_timeout_seconds)
        response.raise_for_status()
        return response.json()

    def step(self) -> dict[str, Any] | None:
        existing = _read_existing(self.output_path)

        previous_state = None
        previous_block = None
        previous_hysteresis_active = False
        previous_episode_id = 0

        if not existing.empty:
            last = existing.iloc[-1]
            previous_state = str(last.get("agent_risk_state", ""))
            previous_block = str(last.get("latest_block", ""))
            previous_hysteresis_active = _safe_bool(last.get("hysteresis_alert_active"))
            previous_episode_id = int(_safe_float(last.get("episode_id"), 0.0))

        payload = self.fetch_current()
        values = _extract_monitor_values(payload)

        latest_block = str(values["latest_block"])

        if (
            not self.log_same_block
            and previous_block
            and latest_block
            and previous_block == latest_block
        ):
            print(f"[counterfactual] skip same block={latest_block}")
            return None

        hyst = apply_hysteresis(
            value=values["composite_dij"],
            previous_alert_active=previous_hysteresis_active,
            enter_threshold=self.enter_threshold,
            exit_threshold=self.exit_threshold,
        )

        episode_id = previous_episode_id
        if hyst.event == "ENTER_ALERT":
            episode_id += 1

        decision = classify_gradient_decision(
            composite_dij=values["composite_dij"],
            tx_dij=values["tx_dij"],
            gas_dij=values["gas_dij"],
            base_fee_dij=values["base_fee_dij"],
            alert_active=hyst.alert_active,
            previous_state=previous_state,
        )

        risk = _risk_metrics(
            composite_dij=values["composite_dij"],
            tx_dij=values["tx_dij"],
            gas_dij=values["gas_dij"],
            base_fee_dij=values["base_fee_dij"],
            alert_active=hyst.alert_active,
        )

        baseline_notional = self.baseline_notional
        baseline_should_execute = True
        baseline_execution_mode = "EXECUTE_FULL"
        baseline_action = "Baseline executes full notional regardless of regime."

        agent_notional = (
            baseline_notional * decision.max_position_multiplier
            if decision.should_execute
            else 0.0
        )

        avoided_notional = max(0.0, baseline_notional - agent_notional)

        baseline_risk_exposure = baseline_notional * risk["execution_risk_score"]
        agent_risk_exposure = agent_notional * risk["execution_risk_score"]
        avoided_risk_exposure = baseline_risk_exposure - agent_risk_exposure

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **values,

            "hysteresis_alert_active": hyst.alert_active,
            "hysteresis_event": hyst.event,
            "episode_id": episode_id,

            "agent_risk_state": decision.risk_state,
            "agent_execution_mode": decision.execution_mode,
            "agent_should_execute": decision.should_execute,
            "agent_notional": agent_notional,
            "agent_action": decision.action,

            "baseline_execution_mode": baseline_execution_mode,
            "baseline_should_execute": baseline_should_execute,
            "baseline_notional": baseline_notional,
            "baseline_action": baseline_action,

            "avoided_notional": avoided_notional,

            **risk,

            "baseline_risk_exposure": baseline_risk_exposure,
            "agent_risk_exposure": agent_risk_exposure,
            "avoided_risk_exposure": avoided_risk_exposure,
        }

        _append_row(self.output_path, row)

        print(
            f"[counterfactual] block={latest_block} "
            f"regime={values['regime']} "
            f"hyst={hyst.event} "
            f"agent={decision.execution_mode} "
            f"risk={decision.risk_state} "
            f"baseline=EXECUTE_FULL "
            f"agent_notional={agent_notional:.2f} "
            f"avoided_risk={avoided_risk_exposure:.4f}"
        )

        return row


def create_counterfactual_logger_from_env() -> CounterfactualLogger:
    return CounterfactualLogger(
        monitor_api_url=os.getenv(
            "MONITOR_API_URL",
            "http://localhost:8001/v1/current",
        ),
        output_path=os.getenv(
            "COUNTERFACTUAL_OUTPUT_PATH",
            "data/counterfactual_log.csv",
        ),
        baseline_notional=float(os.getenv("COUNTERFACTUAL_BASELINE_NOTIONAL", "1.0")),
        request_timeout_seconds=int(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "10")),
        log_same_block=os.getenv("COUNTERFACTUAL_LOG_SAME_BLOCK", "false").lower()
        in {"1", "true", "yes", "on"},
        enter_threshold=float(os.getenv("ALERT_ENTER_THRESHOLD", "1.0")),
        exit_threshold=float(os.getenv("ALERT_EXIT_THRESHOLD", "0.85")),
    )


def run_forever() -> None:
    interval = int(os.getenv("COUNTERFACTUAL_POLL_INTERVAL_SECONDS", "12"))

    logger = create_counterfactual_logger_from_env()

    print("=" * 80)
    print("SUPT Counterfactual Execution Logger")
    print("=" * 80)
    print(f"Monitor API: {logger.monitor_api_url}")
    print(f"Output path: {logger.output_path}")
    print(f"Baseline notional: {logger.baseline_notional}")
    print(f"Poll interval: {interval}s")
    print("=" * 80)

    while True:
        try:
            logger.step()
        except Exception as exc:
            print(f"[counterfactual] error: {type(exc).__name__}: {exc}")

        time.sleep(interval)
