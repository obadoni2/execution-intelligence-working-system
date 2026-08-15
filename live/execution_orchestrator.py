from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
APPROVAL = Path("live/data/policy_approval_deployment.csv")
TRUST = Path("live/data/policy_trust_score.csv")
RECAL = Path("live/data/automatic_policy_recalibration.csv")
OUT = Path("live/data/execution_orchestrator_receipts.csv")

KILL_SWITCH = Path("live/data/KILL_SWITCH_ON")


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
    for row in rows:
        symbol = row.get("symbol")
        if symbol:
            latest[symbol] = row
    return latest


def decide_action(
    risk: Dict[str, Any],
    approval: Dict[str, Any],
    trust: Dict[str, Any],
) -> Dict[str, Any]:
    if KILL_SWITCH.exists():
        return {
            "orchestrator_action": "BLOCKED",
            "execution_route": "NONE",
            "reason": "KILL_SWITCH_ON",
        }

    stage = approval.get("deployment_stage", "DRAFT")
    trust_label = trust.get("policy_trust_label", "UNTRUSTED")
    risk_decision = risk.get("risk_decision", "UNKNOWN")

    if stage == "DRAFT":
        return {
            "orchestrator_action": "NO_ACTION",
            "execution_route": "NONE",
            "reason": "POLICY_IN_DRAFT",
        }

    if trust_label == "UNTRUSTED":
        return {
            "orchestrator_action": "NO_ACTION",
            "execution_route": "NONE",
            "reason": "POLICY_UNTRUSTED",
        }

    if risk_decision in {"BLOCK", "PAUSE"}:
        return {
            "orchestrator_action": "BLOCKED",
            "execution_route": "NONE",
            "reason": f"RISK_GATE_{risk_decision}",
        }

    if stage in {"SIMULATION", "PAPER_TRADING"}:
        return {
            "orchestrator_action": "PAPER_TRADE",
            "execution_route": "PAPER",
            "reason": f"STAGE_{stage}",
        }

    if stage == "LIMITED_LIVE":
        return {
            "orchestrator_action": "READY_FOR_LIMITED_LIVE",
            "execution_route": "LIVE_LIMITED",
            "reason": "LIMITED_LIVE_APPROVED",
        }

    if stage == "PRODUCTION":
        return {
            "orchestrator_action": "READY_FOR_PRODUCTION",
            "execution_route": "LIVE_PRODUCTION",
            "reason": "PRODUCTION_APPROVED",
        }

    return {
        "orchestrator_action": "NO_ACTION",
        "execution_route": "NONE",
        "reason": "UNKNOWN_STAGE",
    }


def main() -> None:
    risk_rows = load_csv(RISK_GATE)
    approval_rows = load_csv(APPROVAL)
    trust_rows = load_csv(TRUST)
    recal_rows = load_csv(RECAL)

    if not risk_rows:
        raise FileNotFoundError(f"No risk gate receipts found at {RISK_GATE}")
    if not approval_rows:
        raise FileNotFoundError(f"No approval deployment data found at {APPROVAL}")
    if not trust_rows:
        raise FileNotFoundError(f"No policy trust score found at {TRUST}")

    latest_risk = latest_by_symbol(risk_rows)
    approval = approval_rows[-1]
    trust = trust_rows[-1]

    recal_updates = sum(1 for r in recal_rows if r.get("recommended_update") != "NO_CHANGE")

    now = datetime.now(timezone.utc).isoformat()
    receipts = []

    for symbol, risk in latest_risk.items():
        decision = decide_action(risk, approval, trust)

        receipts.append({
            "receipt_written_at": now,
            "symbol": symbol,
            "risk_decision": risk.get("risk_decision"),
            "max_size_multiplier": risk.get("max_size_multiplier"),
            "policy_stage": approval.get("deployment_stage"),
            "approval_status": approval.get("approval_status"),
            "capital_percentage": approval.get("capital_percentage"),
            "policy_trust_label": trust.get("policy_trust_label"),
            "policy_trust_score": trust.get("policy_trust_score"),
            "recalibration_updates": recal_updates,
            "kill_switch_on": str(KILL_SWITCH.exists()).upper(),
            **decision,
            "provider_data_hash": risk.get("provider_data_hash"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(receipts[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(receipts)

    print("EXECUTION ORCHESTRATOR COMPLETE")
    print(f"Wrote {len(receipts)} orchestrator receipts to {OUT}")

    for r in receipts:
        print(
            f"{r['symbol']}: {r['orchestrator_action']} "
            f"route={r['execution_route']} reason={r['reason']}"
        )


if __name__ == "__main__":
    main()
