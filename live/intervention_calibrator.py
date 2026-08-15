from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/intervention_calibration.csv")

HORIZON_ROWS = 3
BAD_STRESS_SCORE = 0.50
CAUTION_STRESS_SCORE = 0.25


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


def group_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get("symbol", "UNKNOWN"), []).append(row)
    return grouped


def classify_outcome(decision: str, current_score: float, future_max_score: float) -> Dict[str, Any]:
    future_bad = future_max_score >= BAD_STRESS_SCORE
    future_caution = future_max_score >= CAUTION_STRESS_SCORE

    if decision == "ALLOW":
        if future_bad:
            return {
                "outcome": "MISSED_STRESS",
                "quality_score": 0.0,
                "explanation": "Allowed execution before future high stress.",
            }
        if future_caution:
            return {
                "outcome": "ALLOW_BEFORE_CAUTION",
                "quality_score": 0.5,
                "explanation": "Allowed execution before future caution.",
            }
        return {
            "outcome": "CORRECT_ALLOW",
            "quality_score": 1.0,
            "explanation": "Allowed execution and future stress stayed acceptable.",
        }

    if decision == "REDUCE_SIZE":
        if future_bad or future_caution:
            return {
                "outcome": "CORRECT_REDUCE_SIZE",
                "quality_score": 1.0,
                "explanation": "Reduced size before future stress/caution persisted.",
            }
        return {
            "outcome": "OVERREACTION_REDUCE_SIZE",
            "quality_score": 0.35,
            "explanation": "Reduced size but future stress stayed low.",
        }

    if decision == "PAUSE":
        if future_bad:
            return {
                "outcome": "CORRECT_PAUSE",
                "quality_score": 1.0,
                "explanation": "Paused before future high stress.",
            }
        if future_caution:
            return {
                "outcome": "DEFENSIVE_PAUSE",
                "quality_score": 0.65,
                "explanation": "Paused before future caution but not high stress.",
            }
        return {
            "outcome": "OVERREACTION_PAUSE",
            "quality_score": 0.25,
            "explanation": "Paused but future stress stayed low.",
        }

    if decision == "BLOCK":
        if future_bad:
            return {
                "outcome": "CORRECT_BLOCK",
                "quality_score": 1.0,
                "explanation": "Blocked before future high stress.",
            }
        return {
            "outcome": "OVERREACTION_BLOCK",
            "quality_score": 0.15,
            "explanation": "Blocked but future stress did not become high.",
        }

    return {
        "outcome": "UNKNOWN_DECISION",
        "quality_score": 0.0,
        "explanation": "Unknown risk decision.",
    }


def calibrate() -> List[Dict[str, Any]]:
    rows = load_csv(RISK_GATE)

    if not rows:
        raise FileNotFoundError(f"No risk-gate receipts found at {RISK_GATE}")

    grouped = group_by_symbol(rows)
    output = []

    for symbol, symbol_rows in grouped.items():
        for i, row in enumerate(symbol_rows):
            future = symbol_rows[i + 1 : i + 1 + HORIZON_ROWS]
            if not future:
                continue

            decision = row.get("risk_decision", "UNKNOWN")
            current_score = fnum(row.get("stress_score"))
            future_scores = [fnum(r.get("stress_score")) for r in future]
            future_max_score = max(future_scores) if future_scores else current_score

            result = classify_outcome(decision, current_score, future_max_score)

            output.append({
                "symbol": symbol,
                "receipt_written_at": row.get("receipt_written_at"),
                "risk_decision": decision,
                "current_stress_score": current_score,
                "future_max_stress_score": round(future_max_score, 6),
                "horizon_rows": HORIZON_ROWS,
                "intervention_outcome": result["outcome"],
                "intervention_quality_score": result["quality_score"],
                "explanation": result["explanation"],
                "decision_reason": row.get("decision_reason"),
                "provider_data_hash": row.get("provider_data_hash"),
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(output)

    return output


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    if not total:
        return {}

    avg_quality = sum(fnum(r.get("intervention_quality_score")) for r in rows) / total

    counts: Dict[str, int] = {}
    for r in rows:
        outcome = r.get("intervention_outcome", "UNKNOWN")
        counts[outcome] = counts.get(outcome, 0) + 1

    overreactions = sum(v for k, v in counts.items() if "OVERREACTION" in k)
    missed = counts.get("MISSED_STRESS", 0)
    correct = sum(v for k, v in counts.items() if k.startswith("CORRECT"))

    return {
        "total_calibrated_events": total,
        "average_intervention_quality_score": round(avg_quality, 6),
        "correct_intervention_rate": round(correct / total, 6),
        "overreaction_rate": round(overreactions / total, 6),
        "missed_stress_rate": round(missed / total, 6),
        "outcome_counts": counts,
    }


def main() -> None:
    rows = calibrate()
    summary = summarize(rows)

    print("INTERVENTION CALIBRATION COMPLETE")
    print(summary)
    print(f"Wrote calibration rows to {OUT}")


if __name__ == "__main__":
    main()
