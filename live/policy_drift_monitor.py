from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


COUNTERFACTUAL = Path("live/data/counterfactual_value_analysis.csv")
REGIME_PERF = Path("live/data/regime_performance_tracking.csv")
OUT = Path("live/data/policy_drift_monitor.csv")

MIN_EVENTS = 20


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


def classify_health(total: int, net_value: float, baseline_better: int, policy_better: int) -> Dict[str, Any]:
    if total < MIN_EVENTS:
        return {
            "policy_status": "INSUFFICIENT_DATA",
            "drift_score": 0.0,
            "recalibration_recommendation": "COLLECT_MORE_DATA",
            "reason": "Not enough completed counterfactual events to evaluate drift reliably.",
        }

    baseline_rate = baseline_better / total if total else 0.0
    policy_rate = policy_better / total if total else 0.0
    avg_value = net_value / total if total else 0.0

    drift_score = round(
        max(0.0, baseline_rate - policy_rate) + max(0.0, -avg_value),
        6,
    )

    if drift_score >= 0.50:
        status = "POLICY_DEGRADING"
        rec = "RECALIBRATION_NEEDED"
        reason = "Baseline is outperforming policy or net policy value is negative."
    elif drift_score >= 0.20:
        status = "DRIFT_WARNING"
        rec = "MONITOR_CLOSELY"
        reason = "Early signs of policy degradation detected."
    else:
        status = "POLICY_HEALTHY"
        rec = "KEEP_CURRENT_POLICY"
        reason = "No strong evidence of policy degradation."

    return {
        "policy_status": status,
        "drift_score": drift_score,
        "recalibration_recommendation": rec,
        "reason": reason,
    }


def run() -> List[Dict[str, Any]]:
    rows = load_csv(COUNTERFACTUAL)
    regime_rows = load_csv(REGIME_PERF)

    if not rows:
        raise FileNotFoundError(f"No counterfactual rows found at {COUNTERFACTUAL}")

    total = len(rows)
    policy_better = sum(1 for r in rows if r.get("counterfactual_label") == "POLICY_BETTER_THAN_BASELINE")
    baseline_better = sum(1 for r in rows if r.get("counterfactual_label") == "BASELINE_BETTER_THAN_POLICY")
    roughly_equal = sum(1 for r in rows if r.get("counterfactual_label") == "ROUGHLY_EQUAL")

    net_value = sum(fnum(r.get("net_policy_advantage")) for r in rows)
    loss_avoided = sum(fnum(r.get("loss_avoided_proxy")) for r in rows)
    opportunity_cost = sum(fnum(r.get("opportunity_cost_proxy")) for r in rows)

    health = classify_health(total, net_value, baseline_better, policy_better)

    regime_count = len(regime_rows)
    weak_regimes = sum(1 for r in regime_rows if fnum(r.get("robustness_score")) < 0)
    zero_regimes = sum(1 for r in regime_rows if fnum(r.get("robustness_score")) == 0)

    row = {
        "total_events": total,
        "policy_better": policy_better,
        "baseline_better": baseline_better,
        "roughly_equal": roughly_equal,
        "policy_better_rate": round(policy_better / total, 6) if total else 0.0,
        "baseline_better_rate": round(baseline_better / total, 6) if total else 0.0,
        "roughly_equal_rate": round(roughly_equal / total, 6) if total else 0.0,
        "net_policy_value": round(net_value, 6),
        "avg_policy_value": round(net_value / total, 6) if total else 0.0,
        "loss_avoided_proxy": round(loss_avoided, 6),
        "opportunity_cost_proxy": round(opportunity_cost, 6),
        "regime_groups": regime_count,
        "weak_regime_groups": weak_regimes,
        "zero_signal_regime_groups": zero_regimes,
        **health,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    return [row]


def main() -> None:
    rows = run()
    print("POLICY DRIFT MONITOR COMPLETE")
    print(rows[0])
    print(f"Wrote drift monitor row to {OUT}")


if __name__ == "__main__":
    main()
