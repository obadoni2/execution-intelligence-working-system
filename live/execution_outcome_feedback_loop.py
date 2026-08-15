from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REALISTIC = Path("live/data/realistic_execution_simulation.csv")
OUT = Path("live/data/execution_outcome_feedback_loop.csv")


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest = {}
    for row in rows:
        symbol = row.get("symbol")
        if symbol:
            latest[symbol] = row
    return latest


def classify_feedback(row: Dict[str, Any]) -> Dict[str, Any]:
    status = row.get("execution_status", "UNKNOWN")
    fill_ratio = fnum(row.get("fill_ratio"))
    latency_ms = fnum(row.get("latency_ms"))
    slippage_bps = fnum(row.get("slippage_bps"))
    total_cost = fnum(row.get("total_execution_cost"))
    requested_notional = fnum(row.get("requested_notional"))
    filled_notional = fnum(row.get("filled_notional"))

    cost_rate = total_cost / filled_notional if filled_notional > 0 else 0.0

    execution_quality_score = 0.0

    if status == "FILLED_REALISTIC_EXECUTION":
        execution_quality_score = 1.0
    elif status == "PARTIAL_REALISTIC_EXECUTION":
        execution_quality_score = 0.5
    elif status == "SKIPPED":
        execution_quality_score = 0.0
    else:
        execution_quality_score = -1.0

    latency_penalty = min(latency_ms / 2500.0, 1.0) * 0.25
    slippage_penalty = min(slippage_bps / 50.0, 1.0) * 0.25
    cost_penalty = min(cost_rate / 0.01, 1.0) * 0.25
    fill_bonus = min(fill_ratio, 1.0) * 0.25

    net_execution_score = round(
        execution_quality_score
        + fill_bonus
        - latency_penalty
        - slippage_penalty
        - cost_penalty,
        6,
    )

    if status == "SKIPPED":
        feedback_label = "NO_EXECUTION_FEEDBACK"
        recommended_learning_action = "COLLECT_MORE_EXECUTION_DATA"
    elif net_execution_score >= 0.70:
        feedback_label = "EXECUTION_CONFIRMED"
        recommended_learning_action = "REINFORCE_POLICY"
    elif net_execution_score >= 0.20:
        feedback_label = "EXECUTION_ACCEPTABLE"
        recommended_learning_action = "MONITOR_POLICY"
    elif net_execution_score >= -0.20:
        feedback_label = "EXECUTION_WEAK"
        recommended_learning_action = "REVIEW_POLICY"
    else:
        feedback_label = "EXECUTION_DEGRADED"
        recommended_learning_action = "PENALIZE_POLICY"

    return {
        "execution_quality_score": round(execution_quality_score, 6),
        "latency_penalty": round(latency_penalty, 6),
        "slippage_penalty": round(slippage_penalty, 6),
        "cost_penalty": round(cost_penalty, 6),
        "fill_bonus": round(fill_bonus, 6),
        "net_execution_score": net_execution_score,
        "cost_rate": round(cost_rate, 6),
        "feedback_label": feedback_label,
        "recommended_learning_action": recommended_learning_action,
    }


def main() -> None:
    rows = load_csv(REALISTIC)

    if not rows:
        raise FileNotFoundError(f"No realistic execution rows found at {REALISTIC}")

    latest = latest_by_symbol(rows)
    now = datetime.now(timezone.utc).isoformat()

    outputs = []

    for symbol, row in latest.items():
        feedback = classify_feedback(row)

        outputs.append({
            "feedback_written_at": now,
            "symbol": symbol,
            "paper_trade_id": row.get("paper_trade_id"),
            "execution_status": row.get("execution_status"),
            "fill_status": row.get("fill_status"),
            "requested_notional": row.get("requested_notional"),
            "filled_notional": row.get("filled_notional"),
            "fill_ratio": row.get("fill_ratio"),
            "latency_ms": row.get("latency_ms"),
            "slippage_bps": row.get("slippage_bps"),
            "fee": row.get("fee"),
            "slippage_cost": row.get("slippage_cost"),
            "total_execution_cost": row.get("total_execution_cost"),
            **feedback,
            "policy_stage": row.get("policy_stage"),
            "policy_trust_label": row.get("policy_trust_label"),
            "provider_data_hash": row.get("provider_data_hash"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outputs[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(outputs)

    print("EXECUTION OUTCOME FEEDBACK LOOP COMPLETE")
    print(f"Wrote {len(outputs)} feedback rows to {OUT}")

    for r in outputs:
        print(
            f"{r['symbol']}: {r['feedback_label']} "
            f"net_score={r['net_execution_score']} "
            f"action={r['recommended_learning_action']}"
        )


if __name__ == "__main__":
    main()
