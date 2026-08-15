from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ORCH = Path("live/data/execution_orchestrator_receipts.csv")
RISK = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/execution_intelligence_receipts.csv")


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
    for r in rows:
        symbol = r.get("symbol")
        if symbol:
            latest[symbol] = r
    return latest


def choose_execution_style(risk: Dict[str, Any], orch: Dict[str, Any]) -> Dict[str, Any]:
    spread = fnum(risk.get("spread_bps"))
    depth = fnum(risk.get("top_depth"))
    stress = fnum(risk.get("stress_score"))
    imbalance = abs(fnum(risk.get("trade_imbalance")))
    route = orch.get("execution_route", "NONE")

    if route == "NONE":
        return {
            "execution_style": "NO_EXECUTION",
            "order_type": "NONE",
            "slicing_required": "FALSE",
            "slice_count": 0,
            "urgency": "NONE",
            "reason": "ORCHESTRATOR_BLOCKED_OR_NO_ACTION",
        }

    if stress >= 0.60 or spread >= 8 or depth < 1:
        return {
            "execution_style": "AVOID_OR_WAIT",
            "order_type": "NONE",
            "slicing_required": "FALSE",
            "slice_count": 0,
            "urgency": "LOW",
            "reason": "HIGH_STRESS_WIDE_SPREAD_OR_LOW_DEPTH",
        }

    if spread >= 4 or imbalance >= 0.45:
        return {
            "execution_style": "PASSIVE_LIMIT",
            "order_type": "LIMIT_POST_ONLY",
            "slicing_required": "TRUE",
            "slice_count": 5,
            "urgency": "LOW",
            "reason": "SPREAD_OR_IMBALANCE_REQUIRES_PASSIVE_EXECUTION",
        }

    if depth < 10:
        return {
            "execution_style": "SLICED_LIMIT",
            "order_type": "LIMIT",
            "slicing_required": "TRUE",
            "slice_count": 3,
            "urgency": "MEDIUM",
            "reason": "LIMITED_DEPTH_REQUIRES_SLICING",
        }

    if spread <= 1 and stress < 0.25 and depth >= 10:
        return {
            "execution_style": "AGGRESSIVE_MARKET",
            "order_type": "MARKET",
            "slicing_required": "FALSE",
            "slice_count": 1,
            "urgency": "HIGH",
            "reason": "TIGHT_SPREAD_LOW_STRESS_GOOD_DEPTH",
        }

    return {
        "execution_style": "STANDARD_LIMIT",
        "order_type": "LIMIT",
        "slicing_required": "FALSE",
        "slice_count": 1,
        "urgency": "MEDIUM",
        "reason": "NORMAL_EXECUTION_CONDITIONS",
    }


def main() -> None:
    orch_rows = load_csv(ORCH)
    risk_rows = load_csv(RISK)

    if not orch_rows:
        raise FileNotFoundError(f"No orchestrator receipts found at {ORCH}")

    if not risk_rows:
        raise FileNotFoundError(f"No risk gate receipts found at {RISK}")

    latest_orch = latest_by_symbol(orch_rows)
    latest_risk = latest_by_symbol(risk_rows)

    now = datetime.now(timezone.utc).isoformat()
    outputs = []

    for symbol, orch in latest_orch.items():
        risk = latest_risk.get(symbol, {})
        decision = choose_execution_style(risk, orch)

        outputs.append({
            "receipt_written_at": now,
            "symbol": symbol,
            "orchestrator_action": orch.get("orchestrator_action"),
            "execution_route": orch.get("execution_route"),
            "risk_decision": orch.get("risk_decision"),
            "policy_stage": orch.get("policy_stage"),
            "policy_trust_label": orch.get("policy_trust_label"),
            "spread_bps": risk.get("spread_bps"),
            "top_depth": risk.get("top_depth"),
            "stress_score": risk.get("stress_score"),
            "trade_imbalance": risk.get("trade_imbalance"),
            **decision,
            "provider_data_hash": orch.get("provider_data_hash"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outputs[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(outputs)

    print("EXECUTION INTELLIGENCE COMPLETE")
    print(f"Wrote {len(outputs)} execution intelligence rows to {OUT}")

    for r in outputs:
        print(
            f"{r['symbol']}: {r['execution_style']} "
            f"type={r['order_type']} slices={r['slice_count']} "
            f"reason={r['reason']}"
        )


if __name__ == "__main__":
    main()
