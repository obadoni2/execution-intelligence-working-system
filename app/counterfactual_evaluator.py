from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import pandas as pd


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


def _split_int_csv(value: str | None, default: list[int]) -> list[int]:
    if not value:
        return default

    out: list[int] = []

    for part in value.split(","):
        part = part.strip()
        if part:
            out.append(int(part))

    return out or default


def _is_bad_execution(
    *,
    row: pd.Series,
    bad_risk_threshold: float,
    bad_gas_threshold: float,
    bad_base_fee_threshold: float,
) -> bool:
    risk = _safe_float(row.get("execution_risk_score"))
    gas = _safe_float(row.get("gas_dij"))
    base_fee = _safe_float(row.get("base_fee_dij"))
    composite = _safe_float(row.get("composite_dij"))
    alert = _safe_bool(row.get("hysteresis_alert_active"))

    return (
        risk >= bad_risk_threshold
        or gas >= bad_gas_threshold
        or base_fee >= bad_base_fee_threshold
        or composite >= 1.0
        or alert
    )


def evaluate_counterfactuals_from_env() -> None:
    input_path = Path(os.getenv("COUNTERFACTUAL_OUTPUT_PATH", "data/counterfactual_log.csv"))
    eval_path = Path(os.getenv("COUNTERFACTUAL_EVAL_PATH", "data/counterfactual_eval.csv"))
    summary_path = Path(os.getenv("COUNTERFACTUAL_SUMMARY_PATH", "data/counterfactual_summary.csv"))
    report_path = Path(os.getenv("COUNTERFACTUAL_REPORT_PATH", "data/counterfactual_report.md"))

    horizons = _split_int_csv(
        os.getenv("COUNTERFACTUAL_HORIZONS_BLOCKS"),
        default=[5, 10, 20],
    )

    bad_risk_threshold = float(os.getenv("COUNTERFACTUAL_BAD_RISK_THRESHOLD", "1.0"))
    bad_gas_threshold = float(os.getenv("COUNTERFACTUAL_BAD_GAS_THRESHOLD", "1.0"))
    bad_base_fee_threshold = float(os.getenv("COUNTERFACTUAL_BAD_BASE_FEE_THRESHOLD", "1.0"))

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found. Let the logger run first.")

    df = pd.read_csv(input_path)

    if df.empty:
        raise RuntimeError("Counterfactual log is empty.")

    df["latest_block"] = pd.to_numeric(df["latest_block"], errors="coerce").fillna(0).astype(int)
    df = df.sort_values("latest_block").reset_index(drop=True)

    rows: list[dict[str, Any]] = []

    for _, start in df.iterrows():
        start_block = int(start["latest_block"])

        for horizon in horizons:
            target_block = start_block + horizon
            future_df = df[df["latest_block"] >= target_block]

            if future_df.empty:
                continue

            future = future_df.iloc[0]

            future_bad = _is_bad_execution(
                row=future,
                bad_risk_threshold=bad_risk_threshold,
                bad_gas_threshold=bad_gas_threshold,
                bad_base_fee_threshold=bad_base_fee_threshold,
            )

            baseline_notional = _safe_float(start.get("baseline_notional"), 1.0)
            agent_notional = _safe_float(start.get("agent_notional"), baseline_notional)

            baseline_would_execute_bad = baseline_notional > 0 and future_bad
            agent_would_execute_bad = agent_notional > 0 and future_bad
            agent_avoided_bad = baseline_would_execute_bad and not agent_would_execute_bad

            future_risk = _safe_float(future.get("execution_risk_score"))

            rows.append(
                {
                    "start_block": start_block,
                    "future_block": int(future["latest_block"]),
                    "horizon_blocks": horizon,

                    "start_regime": start.get("regime"),
                    "start_episode_id": start.get("episode_id"),
                    "start_agent_risk_state": start.get("agent_risk_state"),
                    "start_agent_execution_mode": start.get("agent_execution_mode"),

                    "baseline_notional": baseline_notional,
                    "agent_notional": agent_notional,

                    "future_composite_dij": _safe_float(future.get("composite_dij")),
                    "future_gas_dij": _safe_float(future.get("gas_dij")),
                    "future_base_fee_dij": _safe_float(future.get("base_fee_dij")),
                    "future_hysteresis_alert_active": _safe_bool(future.get("hysteresis_alert_active")),
                    "future_execution_risk_score": future_risk,

                    "future_bad_execution": future_bad,
                    "baseline_would_execute_bad": baseline_would_execute_bad,
                    "agent_would_execute_bad": agent_would_execute_bad,
                    "agent_avoided_bad_execution": agent_avoided_bad,

                    "baseline_bad_exposure": baseline_notional * (1.0 if future_bad else 0.0),
                    "agent_bad_exposure": agent_notional * (1.0 if future_bad else 0.0),
                    "avoided_bad_exposure": (baseline_notional - agent_notional) * (1.0 if future_bad else 0.0),

                    "baseline_future_risk_exposure": baseline_notional * future_risk,
                    "agent_future_risk_exposure": agent_notional * future_risk,
                    "avoided_future_risk_exposure": (baseline_notional - agent_notional) * future_risk,
                }
            )

    result = pd.DataFrame(rows)

    if result.empty:
        raise RuntimeError("No evaluable future windows yet. Let logger run longer.")

    eval_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(eval_path, index=False)

    total_baseline_bad = result["baseline_bad_exposure"].sum()
    total_agent_bad = result["agent_bad_exposure"].sum()
    total_avoided_bad = result["avoided_bad_exposure"].sum()

    bad_reduction = 0.0
    if total_baseline_bad > 0:
        bad_reduction = total_avoided_bad / total_baseline_bad

    total_baseline_risk = result["baseline_future_risk_exposure"].sum()
    total_agent_risk = result["agent_future_risk_exposure"].sum()
    total_avoided_risk = result["avoided_future_risk_exposure"].sum()

    risk_reduction = 0.0
    if total_baseline_risk > 0:
        risk_reduction = total_avoided_risk / total_baseline_risk

    grouped = (
        result.groupby(["horizon_blocks", "start_agent_risk_state", "start_agent_execution_mode"])
        .agg(
            rows=("start_block", "count"),
            future_bad_rate=("future_bad_execution", "mean"),
            avoided_bad_count=("agent_avoided_bad_execution", "sum"),
            baseline_bad_exposure=("baseline_bad_exposure", "sum"),
            agent_bad_exposure=("agent_bad_exposure", "sum"),
            avoided_bad_exposure=("avoided_bad_exposure", "sum"),
            baseline_future_risk_exposure=("baseline_future_risk_exposure", "sum"),
            agent_future_risk_exposure=("agent_future_risk_exposure", "sum"),
            avoided_future_risk_exposure=("avoided_future_risk_exposure", "sum"),
        )
        .reset_index()
    )

    grouped.to_csv(summary_path, index=False)

    lines: list[str] = []
    lines.append("# SUPT Counterfactual Execution Report")
    lines.append("")
    lines.append("## Product Question")
    lines.append("")
    lines.append(
        "Did the agent avoid bad execution windows compared with a baseline "
        "that executes full notional every block?"
    )
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"- Evaluated windows: `{len(result)}`")
    lines.append(f"- Total baseline bad exposure: `{total_baseline_bad:.6f}`")
    lines.append(f"- Total agent bad exposure: `{total_agent_bad:.6f}`")
    lines.append(f"- Total avoided bad exposure: `{total_avoided_bad:.6f}`")
    lines.append(f"- Bad execution exposure reduction: `{bad_reduction * 100:.2f}%`")
    lines.append(f"- Total baseline future risk exposure: `{total_baseline_risk:.6f}`")
    lines.append(f"- Total agent future risk exposure: `{total_agent_risk:.6f}`")
    lines.append(f"- Total avoided future risk exposure: `{total_avoided_risk:.6f}`")
    lines.append(f"- Future risk exposure reduction: `{risk_reduction * 100:.2f}%`")
    lines.append("")
    lines.append("## By Horizon / Agent State")
    lines.append("")
    lines.append(grouped.to_markdown(index=False))
    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append(
        "This is a counterfactual proxy report, not live PnL. "
        "It compares the agent branch against a baseline branch using future "
        "gas/regime/risk conditions. Real slippage, gas paid, fill price vs mid, "
        "and transaction success rate can plug into this same structure later."
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 80)
    print("Counterfactual evaluation complete")
    print("=" * 80)
    print(f"Input:   {input_path}")
    print(f"Eval:    {eval_path}")
    print(f"Summary: {summary_path}")
    print(f"Report:  {report_path}")
    print(f"Windows: {len(result)}")
    print(f"Bad exposure reduction: {bad_reduction * 100:.2f}%")
    print(f"Risk exposure reduction: {risk_reduction * 100:.2f}%")
    print("=" * 80)
