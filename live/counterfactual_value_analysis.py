from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


OUTCOMES = Path("live/data/execution_outcome_validation.csv")
OUT = Path("live/data/counterfactual_value_analysis.csv")


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


def best_available_return(row: Dict[str, Any]) -> float:
    vals = [
        fnum(row.get("return_1m_pct")),
        fnum(row.get("return_5m_pct")),
        fnum(row.get("return_15m_pct")),
        fnum(row.get("return_30m_pct")),
    ]
    non_zero = [v for v in vals if v != 0.0]
    return non_zero[-1] if non_zero else 0.0


def counterfactual(row: Dict[str, Any]) -> Dict[str, Any]:
    decision = row.get("risk_decision", "UNKNOWN")
    market_return = best_available_return(row)

    # Do-nothing baseline assumes full exposure.
    do_nothing_exposure = 1.0

    # Policy exposure estimate based on risk decision.
    if decision == "ALLOW":
        policy_exposure = 1.0
    elif decision == "REDUCE_SIZE":
        policy_exposure = 0.25
    elif decision in {"PAUSE", "BLOCK"}:
        policy_exposure = 0.0
    else:
        policy_exposure = 1.0

    baseline_pnl = do_nothing_exposure * market_return
    policy_pnl = policy_exposure * market_return
    net_policy_advantage = policy_pnl - baseline_pnl

    loss_avoided = 0.0
    opportunity_cost = 0.0

    if market_return < 0 and policy_exposure < do_nothing_exposure:
        loss_avoided = abs(baseline_pnl - policy_pnl)

    if market_return > 0 and policy_exposure < do_nothing_exposure:
        opportunity_cost = abs(baseline_pnl - policy_pnl)

    if net_policy_advantage > 0.05:
        label = "POLICY_BETTER_THAN_BASELINE"
    elif net_policy_advantage < -0.05:
        label = "BASELINE_BETTER_THAN_POLICY"
    else:
        label = "ROUGHLY_EQUAL"

    return {
        "decision_time": row.get("decision_time"),
        "symbol": row.get("symbol"),
        "risk_decision": decision,
        "execution_outcome": row.get("execution_outcome"),
        "market_return_pct": round(market_return, 6),
        "baseline_action": "DO_NOTHING_FULL_EXPOSURE",
        "baseline_exposure": do_nothing_exposure,
        "policy_exposure": policy_exposure,
        "baseline_pnl_proxy": round(baseline_pnl, 6),
        "policy_pnl_proxy": round(policy_pnl, 6),
        "loss_avoided_proxy": round(loss_avoided, 6),
        "opportunity_cost_proxy": round(opportunity_cost, 6),
        "net_policy_advantage": round(net_policy_advantage, 6),
        "counterfactual_label": label,
        "decision_reason": row.get("decision_reason"),
        "provider_data_hash": row.get("provider_data_hash"),
    }


def run() -> List[Dict[str, Any]]:
    rows = load_csv(OUTCOMES)
    if not rows:
        raise FileNotFoundError(f"No execution outcome validation rows found at {OUTCOMES}")

    results = [counterfactual(r) for r in rows]

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    return results


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    labels: Dict[str, int] = {}

    for row in rows:
        label = row.get("counterfactual_label", "UNKNOWN")
        labels[label] = labels.get(label, 0) + 1

    loss_avoided = sum(fnum(r.get("loss_avoided_proxy")) for r in rows)
    opportunity_cost = sum(fnum(r.get("opportunity_cost_proxy")) for r in rows)
    net_advantage = sum(fnum(r.get("net_policy_advantage")) for r in rows)

    return {
        "total_counterfactual_events": total,
        "policy_better_count": labels.get("POLICY_BETTER_THAN_BASELINE", 0),
        "baseline_better_count": labels.get("BASELINE_BETTER_THAN_POLICY", 0),
        "roughly_equal_count": labels.get("ROUGHLY_EQUAL", 0),
        "total_loss_avoided_proxy": round(loss_avoided, 6),
        "total_opportunity_cost_proxy": round(opportunity_cost, 6),
        "net_policy_advantage": round(net_advantage, 6),
        "labels": labels,
    }


def main() -> None:
    rows = run()
    summary = summarize(rows)

    print("COUNTERFACTUAL VALUE ANALYSIS COMPLETE")
    print(summary)
    print(f"Wrote rows to {OUT}")


if __name__ == "__main__":
    main()
