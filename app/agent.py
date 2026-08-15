from __future__ import annotations

import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.agent_rules import classify_agent_state


AGENT_FIELDS = [
    "timestamp",
    "chain",
    "latest_block",
    "monitor_status",
    "regime",
    "composite_dij",
    "tx_dij",
    "gas_dij",
    "base_fee_dij",
    "alert_active",
    "risk_state",
    "confidence",
    "execution_mode",
    "should_execute",
    "allow_new_entries",
    "max_position_multiplier",
    "channel_desync",
    "suggested_action",
    "reason",
    "baseline_action",
    "baseline_notional",
    "agent_notional",
    "avoided_notional",
    "execution_risk_score",
    "baseline_risk_exposure",
    "agent_risk_exposure",
    "avoided_risk_exposure",
    "gas_risk_proxy",
    "slippage_risk_proxy",
    "confirmation_risk_proxy",
]


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


def _read_last_agent_row(path: str | Path) -> dict[str, str] | None:
    path = Path(path)

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            if not rows:
                return None
            return rows[-1]
    except Exception:
        return None


def _append_agent_row(path: str | Path, row: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AGENT_FIELDS)

        if not exists:
            writer.writeheader()

        writer.writerow({field: row.get(field, "") for field in AGENT_FIELDS})


def _extract_monitor_values(payload: dict[str, Any]) -> dict[str, Any]:
    dij_data = payload.get("d_ij", {}) or {}
    alert_data = payload.get("alert", {}) or {}

    composite_dij = _safe_float(
        dij_data.get("composite", payload.get("composite_dij"))
    )
    tx_dij = _safe_float(
        dij_data.get("tx_count", payload.get("tx_dij")),
        composite_dij,
    )
    gas_dij = _safe_float(
        dij_data.get("gas", payload.get("gas_dij"))
    )
    base_fee_dij = _safe_float(
        dij_data.get("base_fee", payload.get("base_fee_dij"))
    )

    return {
        "chain": payload.get("chain", "ethereum"),
        "latest_block": payload.get("latest_block", ""),
        "monitor_status": payload.get("status", "unknown"),
        "regime": payload.get("regime", ""),
        "composite_dij": composite_dij,
        "tx_dij": tx_dij,
        "gas_dij": gas_dij,
        "base_fee_dij": base_fee_dij,
        "alert_active": _safe_bool(
            alert_data.get("is_active", payload.get("alert_active"))
        ),
    }


def _execution_risk_score(
    *,
    composite_dij: float,
    tx_dij: float,
    gas_dij: float,
    base_fee_dij: float,
    alert_active: bool,
) -> dict[str, float]:
    """
    Proxy evaluation layer.

    This does not calculate real PnL.
    It estimates execution-risk exposure so we can compare:

    baseline = always execute normally
    agent = execute according to regime state
    """

    gas_risk_proxy = max(gas_dij, base_fee_dij)
    slippage_risk_proxy = max(composite_dij, tx_dij, gas_dij)
    confirmation_risk_proxy = max(composite_dij, base_fee_dij)

    risk = (
        0.40 * composite_dij
        + 0.25 * gas_dij
        + 0.20 * base_fee_dij
        + 0.15 * tx_dij
    )

    if alert_active:
        risk += 0.25

    return {
        "execution_risk_score": risk,
        "gas_risk_proxy": gas_risk_proxy,
        "slippage_risk_proxy": slippage_risk_proxy,
        "confirmation_risk_proxy": confirmation_risk_proxy,
    }


class EthereumRegimeAgent:
    def __init__(
        self,
        *,
        monitor_api_url: str,
        output_path: str,
        request_timeout_seconds: int = 10,
        log_same_block: bool = False,
        baseline_notional: float = 1.0,
    ) -> None:
        self.monitor_api_url = monitor_api_url
        self.output_path = output_path
        self.request_timeout_seconds = request_timeout_seconds
        self.log_same_block = log_same_block
        self.baseline_notional = baseline_notional

    def fetch_current_state(self) -> dict[str, Any]:
        response = requests.get(
            self.monitor_api_url,
            timeout=self.request_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def step(self) -> dict[str, Any] | None:
        previous_row = _read_last_agent_row(self.output_path)
        previous_state = previous_row.get("risk_state") if previous_row else None
        previous_block = previous_row.get("latest_block") if previous_row else None

        payload = self.fetch_current_state()
        values = _extract_monitor_values(payload)

        decision = classify_agent_state(
            current_payload=payload,
            previous_risk_state=previous_state,
        )

        latest_block = str(values["latest_block"])

        if (
            not self.log_same_block
            and previous_block
            and latest_block
            and previous_block == latest_block
            and previous_state == decision.risk_state
        ):
            print(
                f"[agent] skip same block={latest_block} "
                f"risk_state={decision.risk_state}"
            )
            return None

        risk_values = _execution_risk_score(
            composite_dij=values["composite_dij"],
            tx_dij=values["tx_dij"],
            gas_dij=values["gas_dij"],
            base_fee_dij=values["base_fee_dij"],
            alert_active=values["alert_active"],
        )

        baseline_notional = self.baseline_notional

        if decision.should_execute:
            agent_notional = baseline_notional * decision.max_position_multiplier
        else:
            agent_notional = 0.0

        avoided_notional = max(0.0, baseline_notional - agent_notional)

        execution_risk_score = risk_values["execution_risk_score"]

        baseline_risk_exposure = baseline_notional * execution_risk_score
        agent_risk_exposure = agent_notional * execution_risk_score
        avoided_risk_exposure = baseline_risk_exposure - agent_risk_exposure

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **values,
            **decision.to_dict(),
            "baseline_notional": baseline_notional,
            "agent_notional": agent_notional,
            "avoided_notional": avoided_notional,
            "execution_risk_score": execution_risk_score,
            "baseline_risk_exposure": baseline_risk_exposure,
            "agent_risk_exposure": agent_risk_exposure,
            "avoided_risk_exposure": avoided_risk_exposure,
            **risk_values,
        }

        _append_agent_row(self.output_path, row)

        print(
            f"[agent] block={row['latest_block']} "
            f"risk={row['risk_state']} "
            f"mode={row['execution_mode']} "
            f"composite={row['composite_dij']:.4f} "
            f"gas={row['gas_dij']:.4f} "
            f"base_fee={row['base_fee_dij']:.4f} "
            f"agent_notional={row['agent_notional']:.2f} "
            f"avoided_risk={row['avoided_risk_exposure']:.4f}"
        )

        return row


def create_agent_from_env() -> EthereumRegimeAgent:
    monitor_api_url = os.getenv(
        "MONITOR_API_URL",
        "http://localhost:8001/v1/current",
    ).strip()

    output_path = os.getenv(
        "AGENT_OUTPUT_PATH",
        "data/agent_decisions.csv",
    ).strip()

    request_timeout_seconds = int(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "10"))

    log_same_block = os.getenv("AGENT_LOG_SAME_BLOCK", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    baseline_notional = float(os.getenv("AGENT_BASELINE_NOTIONAL", "1.0"))

    return EthereumRegimeAgent(
        monitor_api_url=monitor_api_url,
        output_path=output_path,
        request_timeout_seconds=request_timeout_seconds,
        log_same_block=log_same_block,
        baseline_notional=baseline_notional,
    )


def run_forever() -> None:
    poll_interval = int(os.getenv("AGENT_POLL_INTERVAL_SECONDS", "12"))

    agent = create_agent_from_env()

    print("=" * 80)
    print("SUPT Ethereum Regime Agent")
    print("=" * 80)
    print(f"Monitor API: {agent.monitor_api_url}")
    print(f"Output path: {agent.output_path}")
    print(f"Poll interval: {poll_interval}s")
    print(f"Baseline notional: {agent.baseline_notional}")
    print("=" * 80)

    while True:
        try:
            agent.step()
        except Exception as exc:
            print(f"[agent] error: {type(exc).__name__}: {exc}")

        time.sleep(poll_interval)
