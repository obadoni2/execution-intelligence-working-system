from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


INPUT_PATH = Path("data/agent_decisions.csv")
OUTPUT_PATH = Path("data/decision_outcomes.csv")

HORIZON_ROWS = 10
BAD_THRESHOLD = 1.0


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def load_rows() -> List[Dict[str, Any]]:
    if not INPUT_PATH.exists():
        return []

    with INPUT_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_bad_window(row: Dict[str, Any]) -> bool:
    composite = safe_float(row.get("composite_dij"))
    gas = safe_float(row.get("gas_dij"))
    base_fee = safe_float(row.get("base_fee_dij"))
    alert_active = safe_bool(row.get("alert_active"))
    risk_state = str(row.get("risk_state", "")).upper()

    return (
        composite >= BAD_THRESHOLD
        or gas >= BAD_THRESHOLD
        or base_fee >= BAD_THRESHOLD
        or alert_active
        or risk_state == "HIGH_STRESS"
    )


def evaluate() -> None:
    rows = load_rows()

    if not rows:
        print("No agent decisions found.")
        return

    output = []

    for i, row in enumerate(rows):
        future_rows = rows[i + 1 : i + 1 + HORIZON_ROWS]

        if not future_rows:
            continue

        future_bad_count = sum(1 for r in future_rows if is_bad_window(r))
        future_bad = future_bad_count > 0

        action = str(row.get("execution_mode") or "").upper()
        should_execute = safe_bool(row.get("should_execute"))

        correct = None

        if action == "PAUSE":
            correct = future_bad
        elif action in {"EXECUTE_FULL", "SELECTIVE_EXECUTE", "RESUME_GRADUALLY"}:
            correct = not future_bad
        elif action == "REDUCE_SIZE":
            correct = future_bad

        avoided_risk = safe_float(row.get("avoided_risk_exposure"))
        baseline_risk = safe_float(row.get("baseline_risk_exposure"))
        agent_risk = safe_float(row.get("agent_risk_exposure"))

        output.append(
            {
                "timestamp": row.get("timestamp"),
                "chain": row.get("chain", "eth"),
                "block_number": row.get("latest_block"),
                "risk_state": row.get("risk_state"),
                "action": action,
                "should_execute": should_execute,
                "composite_dij": row.get("composite_dij"),
                "gas_dij": row.get("gas_dij"),
                "base_fee_dij": row.get("base_fee_dij"),
                "confidence": row.get("confidence"),
                "horizon_rows": HORIZON_ROWS,
                "future_bad": future_bad,
                "future_bad_count": future_bad_count,
                "correct": correct,
                "baseline_risk_exposure": baseline_risk,
                "agent_risk_exposure": agent_risk,
                "avoided_risk_exposure": avoided_risk,
                "reason": row.get("reason"),
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

    print(f"Wrote {len(output)} decision outcomes to {OUTPUT_PATH}")


if __name__ == "__main__":
    evaluate()
