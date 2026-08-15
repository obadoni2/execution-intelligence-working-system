from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


TRUST_FILE = Path("live/data/policy_trust_score.csv")
CONFIDENCE_FILE = Path("live/data/evidence_confidence_engine.csv")
RISK_GATE_FILE = Path("live/data/live_risk_gate_receipts.csv")
ORCHESTRATOR_FILE = Path("live/data/execution_orchestrator_receipts.csv")
OUT_FILE = Path("live/data/position_sizing_receipts.csv")

PORTFOLIO_CAPITAL = 10_000.0
MAX_POSITION_PCT = 2.0
MAX_TOTAL_ALLOCATION_PCT = 10.0


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def latest_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        symbol = row.get("symbol")
        if symbol:
            latest[symbol] = row

    return latest


def trust_multiplier(trust_label: str) -> float:
    mapping = {
        "UNTRUSTED": 0.0,
        "LOW_TRUST": 0.20,
        "MODERATE_TRUST": 0.45,
        "HIGH_TRUST": 0.75,
        "PRODUCTION_READY": 1.0,
    }
    return mapping.get(trust_label, 0.0)


def confidence_multiplier(confidence_label: str) -> float:
    mapping = {
        "LOW_CONFIDENCE": 0.25,
        "MEDIUM_CONFIDENCE": 0.60,
        "HIGH_CONFIDENCE": 1.0,
    }
    return mapping.get(confidence_label, 0.0)


def risk_decision_multiplier(risk_decision: str) -> float:
    mapping = {
        "ALLOW": 1.0,
        "REDUCE_SIZE": 0.25,
        "PAUSE": 0.0,
        "BLOCK": 0.0,
    }
    return mapping.get(risk_decision, 0.0)


def stress_multiplier(stress_score: float) -> float:
    if stress_score >= 0.75:
        return 0.0
    if stress_score >= 0.50:
        return 0.25
    if stress_score >= 0.30:
        return 0.60
    return 1.0


def liquidity_multiplier(top_depth: float) -> float:
    if top_depth <= 0:
        return 0.0
    if top_depth < 1:
        return 0.15
    if top_depth < 10:
        return 0.40
    if top_depth < 100:
        return 0.70
    return 1.0


def spread_multiplier(spread_bps: float) -> float:
    if spread_bps >= 10:
        return 0.0
    if spread_bps >= 5:
        return 0.25
    if spread_bps >= 2:
        return 0.60
    return 1.0


def determine_reason(
    trust_label: str,
    confidence_label: str,
    orchestrator_action: str,
    risk_decision: str,
    final_position_pct: float,
) -> str:
    reasons = []

    if trust_label == "UNTRUSTED":
        reasons.append("POLICY_UNTRUSTED")

    if confidence_label == "LOW_CONFIDENCE":
        reasons.append("LOW_EVIDENCE_CONFIDENCE")

    if orchestrator_action in {"NO_ACTION", "BLOCKED"}:
        reasons.append(f"ORCHESTRATOR_{orchestrator_action}")

    if risk_decision in {"PAUSE", "BLOCK"}:
        reasons.append(f"RISK_GATE_{risk_decision}")

    if final_position_pct <= 0 and not reasons:
        reasons.append("POSITION_SIZE_REDUCED_TO_ZERO")

    if not reasons:
        reasons.append("POSITION_SIZE_CALCULATED")

    return ",".join(reasons)


def main() -> None:
    trust_rows = load_csv(TRUST_FILE)
    confidence_rows = load_csv(CONFIDENCE_FILE)
    risk_rows = load_csv(RISK_GATE_FILE)
    orchestrator_rows = load_csv(ORCHESTRATOR_FILE)

    if not trust_rows:
        raise FileNotFoundError(
            f"No policy trust score found at {TRUST_FILE}"
        )

    if not confidence_rows:
        raise FileNotFoundError(
            f"No evidence confidence data found at {CONFIDENCE_FILE}"
        )

    if not risk_rows:
        raise FileNotFoundError(
            f"No risk-gate receipts found at {RISK_GATE_FILE}"
        )

    if not orchestrator_rows:
        raise FileNotFoundError(
            f"No execution orchestrator receipts found at {ORCHESTRATOR_FILE}"
        )

    trust = trust_rows[-1]
    confidence = confidence_rows[-1]

    trust_label = trust.get("policy_trust_label", "UNTRUSTED")
    trust_score = fnum(trust.get("policy_trust_score"))

    confidence_label = confidence.get(
        "evidence_confidence_label",
        "LOW_CONFIDENCE",
    )
    confidence_score = fnum(
        confidence.get("evidence_confidence_score")
    )

    latest_risk = latest_by_symbol(risk_rows)
    latest_orchestrator = latest_by_symbol(orchestrator_rows)

    timestamp = datetime.now(timezone.utc).isoformat()
    receipts: List[Dict[str, Any]] = []

    maximum_total_capital = (
        PORTFOLIO_CAPITAL * MAX_TOTAL_ALLOCATION_PCT / 100.0
    )

    raw_receipts = []

    for symbol, orchestrator in latest_orchestrator.items():
        risk = latest_risk.get(symbol, {})

        risk_decision = orchestrator.get(
            "risk_decision",
            risk.get("risk_decision", "UNKNOWN"),
        )

        orchestrator_action = orchestrator.get(
            "orchestrator_action",
            "NO_ACTION",
        )

        stress_score = fnum(risk.get("stress_score"))
        spread_bps = fnum(risk.get("spread_bps"))
        top_depth = fnum(risk.get("top_depth"))

        base_position_pct = MAX_POSITION_PCT

        trust_factor = trust_multiplier(trust_label)
        confidence_factor = confidence_multiplier(confidence_label)
        risk_factor = risk_decision_multiplier(risk_decision)
        stress_factor = stress_multiplier(stress_score)
        liquidity_factor = liquidity_multiplier(top_depth)
        spread_factor = spread_multiplier(spread_bps)

        if orchestrator_action not in {
            "PAPER_TRADE",
            "READY_FOR_LIMITED_LIVE",
            "READY_FOR_PRODUCTION",
        }:
            orchestrator_factor = 0.0
        else:
            orchestrator_factor = 1.0

        calculated_position_pct = (
            base_position_pct
            * trust_factor
            * confidence_factor
            * risk_factor
            * stress_factor
            * liquidity_factor
            * spread_factor
            * orchestrator_factor
        )

        calculated_position_pct = max(
            0.0,
            min(calculated_position_pct, MAX_POSITION_PCT),
        )

        requested_capital = (
            PORTFOLIO_CAPITAL * calculated_position_pct / 100.0
        )

        raw_receipts.append({
            "symbol": symbol,
            "orchestrator_action": orchestrator_action,
            "execution_route": orchestrator.get("execution_route"),
            "risk_decision": risk_decision,
            "policy_stage": orchestrator.get("policy_stage"),
            "approval_status": orchestrator.get("approval_status"),
            "trust_label": trust_label,
            "trust_score": trust_score,
            "confidence_label": confidence_label,
            "confidence_score": confidence_score,
            "stress_score": stress_score,
            "spread_bps": spread_bps,
            "top_depth": top_depth,
            "base_position_pct": base_position_pct,
            "trust_factor": trust_factor,
            "confidence_factor": confidence_factor,
            "risk_factor": risk_factor,
            "stress_factor": stress_factor,
            "liquidity_factor": liquidity_factor,
            "spread_factor": spread_factor,
            "orchestrator_factor": orchestrator_factor,
            "calculated_position_pct": calculated_position_pct,
            "requested_capital": requested_capital,
            "provider_data_hash": orchestrator.get(
                "provider_data_hash"
            ),
        })

    total_requested_capital = sum(
        row["requested_capital"] for row in raw_receipts
    )

    portfolio_scaling_factor = 1.0

    if (
        total_requested_capital > maximum_total_capital
        and total_requested_capital > 0
    ):
        portfolio_scaling_factor = (
            maximum_total_capital / total_requested_capital
        )

    for row in raw_receipts:
        final_position_pct = (
            row["calculated_position_pct"]
            * portfolio_scaling_factor
        )

        capital_allocated = (
            PORTFOLIO_CAPITAL * final_position_pct / 100.0
        )

        reason = determine_reason(
            trust_label=row["trust_label"],
            confidence_label=row["confidence_label"],
            orchestrator_action=row["orchestrator_action"],
            risk_decision=row["risk_decision"],
            final_position_pct=final_position_pct,
        )

        receipts.append({
            "receipt_written_at": timestamp,
            "symbol": row["symbol"],
            "portfolio_capital": PORTFOLIO_CAPITAL,
            "maximum_position_pct": MAX_POSITION_PCT,
            "maximum_total_allocation_pct": MAX_TOTAL_ALLOCATION_PCT,
            "policy_stage": row["policy_stage"],
            "approval_status": row["approval_status"],
            "orchestrator_action": row["orchestrator_action"],
            "execution_route": row["execution_route"],
            "risk_decision": row["risk_decision"],
            "policy_trust_label": row["trust_label"],
            "policy_trust_score": round(
                row["trust_score"],
                6,
            ),
            "evidence_confidence_label": row["confidence_label"],
            "evidence_confidence_score": round(
                row["confidence_score"],
                6,
            ),
            "stress_score": round(row["stress_score"], 6),
            "spread_bps": round(row["spread_bps"], 6),
            "top_depth": round(row["top_depth"], 6),
            "base_position_pct": round(
                row["base_position_pct"],
                6,
            ),
            "trust_factor": round(row["trust_factor"], 6),
            "confidence_factor": round(
                row["confidence_factor"],
                6,
            ),
            "risk_factor": round(row["risk_factor"], 6),
            "stress_factor": round(row["stress_factor"], 6),
            "liquidity_factor": round(
                row["liquidity_factor"],
                6,
            ),
            "spread_factor": round(row["spread_factor"], 6),
            "orchestrator_factor": round(
                row["orchestrator_factor"],
                6,
            ),
            "portfolio_scaling_factor": round(
                portfolio_scaling_factor,
                6,
            ),
            "final_position_pct": round(
                final_position_pct,
                6,
            ),
            "capital_allocated": round(
                capital_allocated,
                6,
            ),
            "sizing_status": (
                "ALLOCATED"
                if capital_allocated > 0
                else "NO_ALLOCATION"
            ),
            "sizing_reason": reason,
            "provider_data_hash": row["provider_data_hash"],
        })

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT_FILE.exists()

    with OUT_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(receipts[0].keys()),
        )

        if not exists:
            writer.writeheader()

        writer.writerows(receipts)

    total_allocated = sum(
        fnum(row["capital_allocated"])
        for row in receipts
    )

    allocations = sum(
        1 for row in receipts
        if row["sizing_status"] == "ALLOCATED"
    )

    print("POSITION SIZING ENGINE COMPLETE")
    print(f"Symbols evaluated: {len(receipts)}")
    print(f"Allocated positions: {allocations}")
    print(f"Total capital allocated: {total_allocated:.2f}")
    print(f"Wrote receipts to {OUT_FILE}")

    for receipt in receipts:
        print(
            f"{receipt['symbol']}: "
            f"{receipt['sizing_status']} "
            f"size={receipt['final_position_pct']}% "
            f"capital={receipt['capital_allocated']} "
            f"reason={receipt['sizing_reason']}"
        )


if __name__ == "__main__":
    main()
