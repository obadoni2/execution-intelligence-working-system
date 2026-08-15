from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


DRIFT = Path("live/data/policy_drift_monitor.csv")
COUNTERFACTUAL = Path("live/data/counterfactual_value_analysis.csv")
REGIME = Path("live/data/regime_performance_tracking.csv")
RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/evidence_confidence_engine.csv")


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


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "HIGH_CONFIDENCE"
    if score >= 0.45:
        return "MEDIUM_CONFIDENCE"
    return "LOW_CONFIDENCE"


def learning_status(score: float, total_events: int) -> str:
    if total_events < 20:
        return "INSUFFICIENT_EVIDENCE"
    if score < 0.45:
        return "COLLECT_MORE_DATA"
    if score < 0.75:
        return "OBSERVE_MORE"
    return "EVIDENCE_READY"


def run() -> Dict[str, Any]:
    drift_rows = load_csv(DRIFT)
    cf_rows = load_csv(COUNTERFACTUAL)
    regime_rows = load_csv(REGIME)
    risk_rows = load_csv(RISK_GATE)

    if not drift_rows:
        raise FileNotFoundError(f"No policy drift monitor data found at {DRIFT}")

    drift = drift_rows[-1]

    total_events = int(fnum(drift.get("total_events")))
    policy_status = drift.get("policy_status", "UNKNOWN")
    recommendation = drift.get("recalibration_recommendation", "UNKNOWN")
    drift_score = fnum(drift.get("drift_score"))

    symbols = {r.get("symbol") for r in risk_rows if r.get("symbol")}
    regimes = {r.get("environment_bucket") for r in regime_rows if r.get("environment_bucket")}

    completed_outcomes = sum(
        1 for r in cf_rows
        if r.get("counterfactual_label") in {
            "POLICY_BETTER_THAN_BASELINE",
            "BASELINE_BETTER_THAN_POLICY",
            "ROUGHLY_EQUAL",
        }
    )

    sample_score = min(total_events / 100.0, 1.0)
    completion_score = completed_outcomes / total_events if total_events else 0.0
    symbol_score = min(len(symbols) / 10.0, 1.0)
    regime_score = min(len(regimes) / 5.0, 1.0)

    # If drift is low, consistency is high. If drift is high, confidence requires more evidence.
    drift_consistency_score = max(0.0, 1.0 - drift_score)

    confidence_score = round(
        (0.35 * sample_score)
        + (0.25 * completion_score)
        + (0.15 * symbol_score)
        + (0.15 * regime_score)
        + (0.10 * drift_consistency_score),
        6,
    )

    label = confidence_label(confidence_score)
    status = learning_status(confidence_score, total_events)

    row = {
        "policy_status": policy_status,
        "recalibration_recommendation": recommendation,
        "drift_score": drift_score,
        "total_events": total_events,
        "completed_outcomes": completed_outcomes,
        "symbol_coverage": len(symbols),
        "regime_coverage": len(regimes),
        "sample_score": round(sample_score, 6),
        "completion_score": round(completion_score, 6),
        "symbol_score": round(symbol_score, 6),
        "regime_score": round(regime_score, 6),
        "drift_consistency_score": round(drift_consistency_score, 6),
        "evidence_confidence_score": confidence_score,
        "evidence_confidence_label": label,
        "learning_status": status,
        "interpretation": (
            "Confidence measures how strongly the system should trust its current "
            "policy-health conclusion. Low confidence means collect more evidence "
            "before changing policy."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    return row


def main() -> None:
    row = run()
    print("EVIDENCE CONFIDENCE ENGINE COMPLETE")
    print(row)
    print(f"Wrote confidence row to {OUT}")


if __name__ == "__main__":
    main()
