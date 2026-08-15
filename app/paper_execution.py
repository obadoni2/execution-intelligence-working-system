from __future__ import annotations

import csv
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PAPER_FIELDS = [
    "paper_timestamp",
    "source_id",
    "source_timestamp",
    "chain",
    "latest_block",
    "block_hash",

    "branch",
    "risk_state",
    "execution_mode",
    "action",
    "notional",
    "executed",

    "regime",
    "composite_dij",
    "tx_dij",
    "gas_dij",
    "base_fee_dij",
    "hysteresis_alert_active",

    "execution_risk_score",
    "gas_pressure_proxy",
    "slippage_pressure_proxy",
    "confirmation_delay_proxy",
    "failed_tx_risk_proxy",

    "paper_gas_paid_proxy",
    "paper_slippage_proxy",
    "paper_failed_tx_cost_proxy",
    "paper_confirmation_delay_blocks_proxy",
    "paper_execution_cost_proxy",

    "opportunity_capture_proxy",
    "notes",
]


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

    try:
        return bool(value)
    except Exception:
        return default


def _read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _append_rows(path: str | Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    exists = path.exists()

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)

        if not exists:
            writer.writeheader()

        for row in rows:
            writer.writerow({field: row.get(field, "") for field in PAPER_FIELDS})


def _source_id(row: pd.Series) -> str:
    return f"{row.get('latest_block', '')}_{row.get('timestamp', '')}"


def _compute_execution_metrics(
    *,
    notional: float,
    executed: bool,
    execution_risk_score: float,
    gas_pressure_proxy: float,
    slippage_pressure_proxy: float,
    failed_tx_risk_proxy: float,
) -> dict[str, float]:
    gas_weight = _safe_float(os.getenv("PAPER_GAS_COST_WEIGHT"), 1.0)
    slippage_weight = _safe_float(os.getenv("PAPER_SLIPPAGE_WEIGHT"), 1.0)
    failed_weight = _safe_float(os.getenv("PAPER_FAILED_TX_WEIGHT"), 1.0)
    delay_weight = _safe_float(os.getenv("PAPER_CONFIRMATION_DELAY_WEIGHT"), 0.10)

    if not executed or notional <= 0:
        return {
            "paper_gas_paid_proxy": 0.0,
            "paper_slippage_proxy": 0.0,
            "paper_failed_tx_cost_proxy": 0.0,
            "paper_confirmation_delay_blocks_proxy": 0.0,
            "paper_execution_cost_proxy": 0.0,
            "opportunity_capture_proxy": 0.0,
        }

    gas_paid = notional * gas_pressure_proxy * gas_weight

    slippage_pressure = max(0.0, slippage_pressure_proxy - 0.75)
    slippage = notional * slippage_pressure * slippage_weight

    failed_tx_cost = notional * failed_tx_risk_proxy * failed_weight

    confirmation_delay_blocks = max(
        1.0,
        1.0 + (execution_risk_score * 2.0) + (gas_pressure_proxy * 2.0),
    )

    confirmation_delay_cost = (
        notional * confirmation_delay_blocks * delay_weight
    )

    total_cost = gas_paid + slippage + failed_tx_cost + confirmation_delay_cost

    return {
        "paper_gas_paid_proxy": gas_paid,
        "paper_slippage_proxy": slippage,
        "paper_failed_tx_cost_proxy": failed_tx_cost,
        "paper_confirmation_delay_blocks_proxy": confirmation_delay_blocks,
        "paper_execution_cost_proxy": total_cost,
        "opportunity_capture_proxy": notional,
    }


def _make_branch_row(
    *,
    source: pd.Series,
    branch: str,
    risk_state: str,
    execution_mode: str,
    action: str,
    notional: float,
) -> dict[str, Any]:
    executed = notional > 0

    execution_risk_score = _safe_float(source.get("execution_risk_score"))
    gas_pressure_proxy = _safe_float(source.get("gas_pressure_proxy"))
    slippage_pressure_proxy = _safe_float(source.get("slippage_pressure_proxy"))
    failed_tx_risk_proxy = _safe_float(source.get("failed_tx_risk_proxy"))

    metrics = _compute_execution_metrics(
        notional=notional,
        executed=executed,
        execution_risk_score=execution_risk_score,
        gas_pressure_proxy=gas_pressure_proxy,
        slippage_pressure_proxy=slippage_pressure_proxy,
        failed_tx_risk_proxy=failed_tx_risk_proxy,
    )

    return {
        "paper_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_id": _source_id(source),
        "source_timestamp": source.get("timestamp"),
        "chain": source.get("chain", "ethereum"),
        "latest_block": source.get("latest_block"),
        "block_hash": source.get("block_hash", ""),

        "branch": branch,
        "risk_state": risk_state,
        "execution_mode": execution_mode,
        "action": action,
        "notional": notional,
        "executed": executed,

        "regime": source.get("regime", ""),
        "composite_dij": _safe_float(source.get("composite_dij")),
        "tx_dij": _safe_float(source.get("tx_dij")),
        "gas_dij": _safe_float(source.get("gas_dij")),
        "base_fee_dij": _safe_float(source.get("base_fee_dij")),
        "hysteresis_alert_active": _safe_bool(source.get("hysteresis_alert_active")),

        "execution_risk_score": execution_risk_score,
        "gas_pressure_proxy": gas_pressure_proxy,
        "slippage_pressure_proxy": slippage_pressure_proxy,
        "confirmation_delay_proxy": _safe_float(source.get("confirmation_delay_proxy")),
        "failed_tx_risk_proxy": failed_tx_risk_proxy,

        **metrics,

        "notes": "Paper execution proxy. No real trade was placed.",
    }


def sync_paper_execution_once_from_env() -> None:
    input_path = Path(os.getenv("PAPER_EXECUTION_INPUT_PATH", "data/counterfactual_log.csv"))
    output_path = Path(os.getenv("PAPER_EXECUTION_OUTPUT_PATH", "data/paper_execution_log.csv"))

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found. Let counterfactual logger run first.")

    source_df = pd.read_csv(input_path)

    if source_df.empty:
        print("[paper] source counterfactual log is empty")
        return

    existing = _read_csv(output_path)

    existing_ids: set[str] = set()

    if not existing.empty and "source_id" in existing.columns:
        existing_ids = set(existing["source_id"].astype(str).unique())

    new_rows: list[dict[str, Any]] = []

    for _, source in source_df.iterrows():
        sid = _source_id(source)

        if sid in existing_ids:
            continue

        baseline_notional = _safe_float(source.get("baseline_notional"), 1.0)
        agent_notional = _safe_float(source.get("agent_notional"), baseline_notional)

        baseline_row = _make_branch_row(
            source=source,
            branch="baseline",
            risk_state="BASELINE",
            execution_mode="EXECUTE_FULL",
            action="Baseline executes full notional regardless of regime.",
            notional=baseline_notional,
        )

        agent_row = _make_branch_row(
            source=source,
            branch="agent",
            risk_state=str(source.get("agent_risk_state", "UNKNOWN")),
            execution_mode=str(source.get("agent_execution_mode", "UNKNOWN")),
            action=str(source.get("agent_action", "")),
            notional=agent_notional,
        )

        new_rows.extend([baseline_row, agent_row])

    _append_rows(output_path, new_rows)

    print("=" * 80)
    print("Paper execution sync complete")
    print("=" * 80)
    print(f"Input:       {input_path}")
    print(f"Output:      {output_path}")
    print(f"New records: {len(new_rows)}")
    print("=" * 80)


def run_forever() -> None:
    interval = int(os.getenv("PAPER_EXECUTION_POLL_INTERVAL_SECONDS", "12"))

    print("=" * 80)
    print("SUPT Paper Execution Logger")
    print("=" * 80)
    print(f"Input:  {os.getenv('PAPER_EXECUTION_INPUT_PATH', 'data/counterfactual_log.csv')}")
    print(f"Output: {os.getenv('PAPER_EXECUTION_OUTPUT_PATH', 'data/paper_execution_log.csv')}")
    print(f"Poll interval: {interval}s")
    print("=" * 80)

    while True:
        try:
            sync_paper_execution_once_from_env()
        except Exception as exc:
            print(f"[paper] error: {type(exc).__name__}: {exc}")

        time.sleep(interval)
