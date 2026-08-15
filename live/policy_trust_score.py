from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


EVIDENCE = Path("live/data/evidence_confidence_engine.csv")
DRIFT = Path("live/data/policy_drift_monitor.csv")
REGIME = Path("live/data/regime_performance_tracking.csv")
COUNTERFACTUAL = Path("live/data/counterfactual_value_analysis.csv")
OUT = Path("live/data/policy_trust_score.csv")


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


def trust_label(score: float, total_events: int) -> str:
    if total_events < 20:
        return "UNTRUSTED"
    if score >= 0.85:
        return "PRODUCTION_READY"
    if score >= 0.70:
        return "HIGH_TRUST"
    if score >= 0.50:
        return "MODERATE_TRUST"
    if score >= 0.30:
        return "LOW_TRUST"
    return "UNTRUSTED"


def run() -> Dict[str, Any]:
    evidence_rows = load_csv(EVIDENCE)
    drift_rows = load_csv(DRIFT)
    regime_rows = load_csv(REGIME)
    cf_rows = load_csv(COUNTERFACTUAL)

    if not evidence_rows:
        raise FileNotFoundError(f"No evidence confidence data found at {EVIDENCE}")
    if not drift_rows:
        raise FileNotFoundError(f"No policy drift data found at {DRIFT}")
    if not cf_rows:
        raise FileNotFoundError(f"No counterfactual data found at {COUNTERFACTUAL}")

    evidence = evidence_rows[-1]
    drift = drift_rows[-1]

    total_events = int(fnum(evidence.get("total_events")))
    evidence_score = fnum(evidence.get("evidence_confidence_score"))
    drift_score = fnum(drift.get("drift_score"))

    policy_better = sum(
        1 for r in cf_rows
        if r.get("counterfactual_label") == "POLICY_BETTER_THAN_BASELINE"
    )
    baseline_better = sum(
        1 for r in cf_rows
        if r.get("counterfactual_label") == "BASELINE_BETTER_THAN_POLICY"
    )
    roughly_equal = sum(
        1 for r in cf_rows
        if r.get("counterfactual_label") == "ROUGHLY_EQUAL"
    )

    net_policy_advantage = sum(fnum(r.get("net_policy_advantage")) for r in cf_rows)
    avg_policy_advantage = net_policy_advantage / len(cf_rows) if cf_rows else 0.0

    counterfactual_score = 0.0
    if cf_rows:
        counterfactual_score = max(
            0.0,
            min(
                1.0,
                0.5
                + (policy_better / len(cf_rows)) * 0.5
                - (baseline_better / len(cf_rows)) * 0.5
                + max(min(avg_policy_advantage, 0.5), -0.5),
            ),
        )

    regime_scores = [fnum(r.get("robustness_score")) for r in regime_rows]
    regime_coverage = len(regime_rows)
    positive_regimes = sum(1 for s in regime_scores if s > 0)
    negative_regimes = sum(1 for s in regime_scores if s < 0)

    regime_score = 0.0
    if regime_rows:
        regime_score = max(
            0.0,
            min(
                1.0,
                0.4
                + min(regime_coverage / 5.0, 1.0) * 0.3
                + (positive_regimes / len(regime_rows)) * 0.2
                - (negative_regimes / len(regime_rows)) * 0.3,
            ),
        )

    sample_score = min(total_events / 100.0, 1.0)
    drift_health_score = max(0.0, 1.0 - drift_score)

    trust_score = round(
        (0.30 * evidence_score)
        + (0.20 * drift_health_score)
        + (0.20 * regime_score)
        + (0.20 * counterfactual_score)
        + (0.10 * sample_score),
        6,
    )

    label = trust_label(trust_score, total_events)

    if label == "UNTRUSTED":
        action = "DO_NOT_DEPLOY_POLICY_CHANGES"
    elif label == "LOW_TRUST":
        action = "KEEP_CURRENT_RULES_AND_COLLECT_MORE_DATA"
    elif label == "MODERATE_TRUST":
        action = "ALLOW_REVIEW_ONLY_RECOMMENDATIONS"
    elif label == "HIGH_TRUST":
        action = "ALLOW_LIMITED_POLICY_RECOMMENDATIONS"
    else:
        action = "POLICY_CAN_BE_CONSIDERED_FOR_PRODUCTION_REVIEW"

    row = {
        "policy_trust_score": trust_score,
        "policy_trust_label": label,
        "recommended_action": action,
        "total_events": total_events,
        "evidence_confidence_score": round(evidence_score, 6),
        "drift_score": round(drift_score, 6),
        "drift_health_score": round(drift_health_score, 6),
        "regime_score": round(regime_score, 6),
        "counterfactual_score": round(counterfactual_score, 6),
        "sample_score": round(sample_score, 6),
        "policy_better": policy_better,
        "baseline_better": baseline_better,
        "roughly_equal": roughly_equal,
        "net_policy_advantage": round(net_policy_advantage, 6),
        "avg_policy_advantage": round(avg_policy_advantage, 6),
        "regime_groups": regime_coverage,
        "positive_regimes": positive_regimes,
        "negative_regimes": negative_regimes,
        "interpretation": (
            "Policy Trust Score estimates whether the current policy has earned enough "
            "evidence to guide future decisions. It combines evidence confidence, drift, "
            "regime coverage, counterfactual value, and sample size."
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
    print("POLICY TRUST SCORE COMPLETE")
    print(row)
    print(f"Wrote trust score row to {OUT}")


if __name__ == "__main__":
    main()
