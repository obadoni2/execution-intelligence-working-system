from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


TRUST = Path("live/data/policy_trust_score.csv")
DRIFT = Path("live/data/policy_drift_monitor.csv")
REGIME = Path("live/data/regime_performance_tracking.csv")
COUNTERFACTUAL = Path("live/data/counterfactual_value_analysis.csv")
OUT = Path("live/data/automatic_policy_recalibration.csv")


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


def recommended_multiplier(action: str, current_multiplier: float, trust_label: str) -> float:
    if trust_label in {"UNTRUSTED", "LOW_TRUST"}:
        return current_multiplier

    if action == "REDUCE_SIZE":
        return max(0.10, current_multiplier * 0.75)

    if action == "PAUSE":
        return 0.0

    if action == "BLOCK":
        return 0.0

    if action == "ALLOW":
        return min(1.0, current_multiplier * 1.10)

    return current_multiplier


def classify_recalibration(
    trust_label: str,
    drift_score: float,
    robustness_score: float,
    baseline_better_rate: float,
    samples: int,
) -> Dict[str, Any]:
    if samples < 20:
        return {
            "recalibration_status": "INSUFFICIENT_DATA",
            "recommended_update": "NO_CHANGE",
            "reason": "Not enough samples to justify recalibration.",
        }

    if trust_label in {"UNTRUSTED", "LOW_TRUST"}:
        return {
            "recalibration_status": "NOT_TRUSTED_FOR_UPDATE",
            "recommended_update": "NO_CHANGE",
            "reason": "Policy has not earned enough trust for automatic recalibration.",
        }

    if drift_score >= 0.50 or baseline_better_rate >= 0.35 or robustness_score < -0.10:
        return {
            "recalibration_status": "RECALIBRATION_RECOMMENDED",
            "recommended_update": "REDUCE_RISK",
            "reason": "Evidence suggests policy degradation or baseline outperformance.",
        }

    if drift_score >= 0.20 or baseline_better_rate >= 0.20:
        return {
            "recalibration_status": "WATCHLIST",
            "recommended_update": "REVIEW_ONLY",
            "reason": "Early signs of drift or weaker policy performance.",
        }

    return {
        "recalibration_status": "POLICY_STABLE",
        "recommended_update": "NO_CHANGE",
        "reason": "No strong evidence requiring recalibration.",
    }


def run() -> List[Dict[str, Any]]:
    trust_rows = load_csv(TRUST)
    drift_rows = load_csv(DRIFT)
    regime_rows = load_csv(REGIME)
    cf_rows = load_csv(COUNTERFACTUAL)

    if not trust_rows:
        raise FileNotFoundError(f"No policy trust score found at {TRUST}")
    if not drift_rows:
        raise FileNotFoundError(f"No policy drift data found at {DRIFT}")
    if not regime_rows:
        raise FileNotFoundError(f"No regime performance data found at {REGIME}")

    trust = trust_rows[-1]
    drift = drift_rows[-1]

    trust_label = trust.get("policy_trust_label", "UNTRUSTED")
    trust_score = fnum(trust.get("policy_trust_score"))
    drift_score = fnum(drift.get("drift_score"))

    outputs = []

    for row in regime_rows:
        env = row.get("environment_bucket", "UNKNOWN")
        action = row.get("risk_decision", "UNKNOWN")
        samples = int(fnum(row.get("samples")))
        robustness_score = fnum(row.get("robustness_score"))
        baseline_better_rate = fnum(row.get("baseline_better_rate"))
        policy_better_rate = fnum(row.get("policy_better_rate"))

        current_multiplier = 1.0
        if action == "REDUCE_SIZE":
            current_multiplier = 0.25
        elif action in {"PAUSE", "BLOCK"}:
            current_multiplier = 0.0

        decision = classify_recalibration(
            trust_label=trust_label,
            drift_score=drift_score,
            robustness_score=robustness_score,
            baseline_better_rate=baseline_better_rate,
            samples=samples,
        )

        proposed_multiplier = recommended_multiplier(
            action=action,
            current_multiplier=current_multiplier,
            trust_label=trust_label,
        )

        if decision["recommended_update"] == "REDUCE_RISK":
            proposed_multiplier = max(0.0, current_multiplier * 0.75)

        outputs.append({
            "environment_bucket": env,
            "risk_decision": action,
            "samples": samples,
            "policy_trust_label": trust_label,
            "policy_trust_score": round(trust_score, 6),
            "drift_score": round(drift_score, 6),
            "robustness_score": round(robustness_score, 6),
            "policy_better_rate": round(policy_better_rate, 6),
            "baseline_better_rate": round(baseline_better_rate, 6),
            "current_size_multiplier": round(current_multiplier, 6),
            "proposed_size_multiplier": round(proposed_multiplier, 6),
            "recalibration_status": decision["recalibration_status"],
            "recommended_update": decision["recommended_update"],
            "reason": decision["reason"],
            "deployment_mode": "RECOMMENDATION_ONLY",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outputs[0].keys()))
        writer.writeheader()
        writer.writerows(outputs)

    return outputs


def main() -> None:
    rows = run()
    print("AUTOMATIC POLICY RECALIBRATION COMPLETE")
    print(f"Wrote {len(rows)} recalibration recommendations to {OUT}")

    for r in rows:
        print(
            f"{r['environment_bucket']} | {r['risk_decision']} | "
            f"{r['recalibration_status']} | {r['recommended_update']} | "
            f"{r['current_size_multiplier']} -> {r['proposed_size_multiplier']}"
        )


if __name__ == "__main__":
    main()
