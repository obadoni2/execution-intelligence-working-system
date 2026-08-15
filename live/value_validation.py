from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


CALIBRATION = Path("live/data/intervention_calibration.csv")
OUT = Path("live/data/value_validation.csv")


VALUE_WEIGHTS = {
    "CORRECT_ALLOW": 1.0,
    "CORRECT_REDUCE_SIZE": 1.5,
    "CORRECT_PAUSE": 2.0,
    "CORRECT_BLOCK": 2.5,
    "ALLOW_BEFORE_CAUTION": -0.5,
    "MISSED_STRESS": -2.5,
    "OVERREACTION_REDUCE_SIZE": -0.75,
    "OVERREACTION_PAUSE": -1.5,
    "OVERREACTION_BLOCK": -2.0,
    "DEFENSIVE_PAUSE": 0.5,
}


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def classify_value(row: Dict[str, Any]) -> Dict[str, Any]:
    outcome = row.get("intervention_outcome", "UNKNOWN")
    risk_decision = row.get("risk_decision", "UNKNOWN")
    current_score = fnum(row.get("current_stress_score"))
    future_score = fnum(row.get("future_max_stress_score"))
    quality = fnum(row.get("intervention_quality_score"))

    base_value = VALUE_WEIGHTS.get(outcome, 0.0)

    stress_delta = max(future_score - current_score, 0.0)

    # Estimate value versus do-nothing baseline.
    if risk_decision in {"REDUCE_SIZE", "PAUSE", "BLOCK"}:
        protected_exposure = {
            "REDUCE_SIZE": 0.75,
            "PAUSE": 1.0,
            "BLOCK": 1.0,
        }.get(risk_decision, 0.0)

        avoided_risk_value = protected_exposure * stress_delta * 10.0
    else:
        avoided_risk_value = 0.0

    overreaction_cost = abs(base_value) if "OVERREACTION" in outcome else 0.0
    missed_stress_cost = abs(base_value) if outcome == "MISSED_STRESS" else 0.0

    net_decision_value = round(base_value + avoided_risk_value - overreaction_cost - missed_stress_cost, 6)

    if net_decision_value > 0.5:
        value_label = "POSITIVE_VALUE"
    elif net_decision_value < -0.5:
        value_label = "NEGATIVE_VALUE"
    else:
        value_label = "NEUTRAL_VALUE"

    return {
        "symbol": row.get("symbol"),
        "receipt_written_at": row.get("receipt_written_at"),
        "risk_decision": risk_decision,
        "intervention_outcome": outcome,
        "current_stress_score": current_score,
        "future_max_stress_score": future_score,
        "intervention_quality_score": quality,
        "baseline_action": "DO_NOTHING",
        "estimated_base_value": base_value,
        "estimated_avoided_risk_value": round(avoided_risk_value, 6),
        "estimated_overreaction_cost": round(overreaction_cost, 6),
        "estimated_missed_stress_cost": round(missed_stress_cost, 6),
        "net_decision_value": net_decision_value,
        "value_label": value_label,
        "decision_reason": row.get("decision_reason"),
        "provider_data_hash": row.get("provider_data_hash"),
    }


def validate() -> List[Dict[str, Any]]:
    rows = load_csv(CALIBRATION)
    if not rows:
        raise FileNotFoundError(f"No calibration rows found at {CALIBRATION}")

    output = [classify_value(r) for r in rows]

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

    return output


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    net_value = sum(fnum(r.get("net_decision_value")) for r in rows)
    positive = sum(1 for r in rows if r.get("value_label") == "POSITIVE_VALUE")
    negative = sum(1 for r in rows if r.get("value_label") == "NEGATIVE_VALUE")
    neutral = sum(1 for r in rows if r.get("value_label") == "NEUTRAL_VALUE")

    return {
        "total_value_events": total,
        "positive_value_events": positive,
        "negative_value_events": negative,
        "neutral_value_events": neutral,
        "positive_value_rate": round(positive / total, 6) if total else 0.0,
        "negative_value_rate": round(negative / total, 6) if total else 0.0,
        "net_policy_value_score": round(net_value, 6),
        "average_value_per_decision": round(net_value / total, 6) if total else 0.0,
    }


def main() -> None:
    rows = validate()
    summary = summarize(rows)

    print("VALUE VALIDATION COMPLETE")
    print(summary)
    print(f"Wrote value validation rows to {OUT}")


if __name__ == "__main__":
    main()
