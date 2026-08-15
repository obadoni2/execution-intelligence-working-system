from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


COUNTERFACTUAL = Path("live/data/counterfactual_value_analysis.csv")
RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/regime_performance_tracking.csv")


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


def build_risk_lookup(rows: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    lookup = {}
    for r in rows:
        lookup[(r.get("receipt_written_at"), r.get("symbol"))] = r
    return lookup


def bucket_market(row: Dict[str, Any]) -> str:
    regime = row.get("regime", "UNKNOWN")
    spread = fnum(row.get("spread_bps"))
    depth = fnum(row.get("top_depth"))
    stress = fnum(row.get("stress_score"))

    if stress >= 0.50:
        return "HIGH_STRESS_ENV"
    if spread >= 5:
        return "HIGH_SPREAD_ENV"
    if depth < 1:
        return "LOW_DEPTH_ENV"
    if regime == "CAUTION":
        return "CAUTION_ENV"
    return "NORMAL_ENV"


def main() -> None:
    cf_rows = load_csv(COUNTERFACTUAL)
    risk_rows = load_csv(RISK_GATE)

    if not cf_rows:
        raise FileNotFoundError(f"No counterfactual rows found at {COUNTERFACTUAL}")

    if not risk_rows:
        raise FileNotFoundError(f"No risk gate rows found at {RISK_GATE}")

    risk_lookup = build_risk_lookup(risk_rows)

    grouped: Dict[tuple, List[Dict[str, Any]]] = {}

    for cf in cf_rows:
        key = (cf.get("decision_time"), cf.get("symbol"))
        risk = risk_lookup.get(key, {})

        merged = {**cf, **risk}
        env = bucket_market(merged)
        action = merged.get("risk_decision", "UNKNOWN")

        grouped.setdefault((env, action), []).append(merged)

    outputs = []

    for (env, action), rows in grouped.items():
        n = len(rows)
        policy_better = sum(1 for r in rows if r.get("counterfactual_label") == "POLICY_BETTER_THAN_BASELINE")
        baseline_better = sum(1 for r in rows if r.get("counterfactual_label") == "BASELINE_BETTER_THAN_POLICY")
        roughly_equal = sum(1 for r in rows if r.get("counterfactual_label") == "ROUGHLY_EQUAL")

        net_advantage = sum(fnum(r.get("net_policy_advantage")) for r in rows)
        loss_avoided = sum(fnum(r.get("loss_avoided_proxy")) for r in rows)
        opportunity_cost = sum(fnum(r.get("opportunity_cost_proxy")) for r in rows)

        robustness_score = 0.0
        if n:
            robustness_score = (
                (policy_better / n)
                - (baseline_better / n)
                + min(net_advantage / max(n, 1), 1.0)
            )

        outputs.append({
            "environment_bucket": env,
            "risk_decision": action,
            "samples": n,
            "policy_better": policy_better,
            "baseline_better": baseline_better,
            "roughly_equal": roughly_equal,
            "policy_better_rate": round(policy_better / n, 6) if n else 0,
            "baseline_better_rate": round(baseline_better / n, 6) if n else 0,
            "net_policy_advantage": round(net_advantage, 6),
            "loss_avoided_proxy": round(loss_avoided, 6),
            "opportunity_cost_proxy": round(opportunity_cost, 6),
            "robustness_score": round(robustness_score, 6),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outputs[0].keys()))
        writer.writeheader()
        writer.writerows(outputs)

    print(f"Wrote {len(outputs)} regime performance rows to {OUT}")

    for row in outputs:
        print(
            f"{row['environment_bucket']} | {row['risk_decision']} | "
            f"samples={row['samples']} score={row['robustness_score']}"
        )


if __name__ == "__main__":
    main()
