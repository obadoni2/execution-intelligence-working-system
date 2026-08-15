from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
SNAPSHOTS = Path("live/data/gateio_market_snapshots.csv")
OUT = Path("live/data/execution_outcome_validation.csv")

HORIZON_MINUTES = [1, 5, 15, 30]


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def parse_dt(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def nearest_future_snapshot(
    snapshots: List[Dict[str, Any]],
    symbol: str,
    decision_time: datetime,
    horizon_minutes: int,
) -> Optional[Dict[str, Any]]:
    target_seconds = horizon_minutes * 60
    candidates = []

    for row in snapshots:
        if row.get("symbol") != symbol:
            continue

        ts = parse_dt(row.get("timestamp_utc", ""))
        if ts is None:
            continue

        delta = (ts - decision_time).total_seconds()

        if delta >= target_seconds:
            candidates.append((delta, row))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def classify_outcome(decision: str, returns: Dict[str, Optional[float]]) -> Dict[str, Any]:
    valid_returns = [v for v in returns.values() if v is not None]

    if not valid_returns:
        return {
            "execution_outcome": "PENDING",
            "protection_score": 0.0,
            "opportunity_score": 0.0,
            "outcome_note": "Not enough future market data yet.",
        }

    min_ret = min(valid_returns)
    max_ret = max(valid_returns)

    protection_score = 0.0
    opportunity_score = 0.0

    if decision in {"REDUCE_SIZE", "PAUSE", "BLOCK"}:
        if min_ret < -0.20:
            protection_score = min(abs(min_ret) / 2.0, 1.0)
            outcome = "PROTECTION_CONFIRMED"
            note = "Defensive decision was followed by adverse price movement."
        elif max_ret > 0.20:
            opportunity_score = min(max_ret / 2.0, 1.0)
            outcome = "OPPORTUNITY_COST"
            note = "Defensive decision was followed by favorable price movement."
        else:
            outcome = "DEFENSIVE_NEUTRAL"
            note = "Defensive decision was followed by mostly neutral movement."

    elif decision == "ALLOW":
        if min_ret < -0.20:
            outcome = "ALLOW_ADVERSE"
            note = "Allowed execution before adverse price movement."
        elif max_ret > 0.20:
            opportunity_score = min(max_ret / 2.0, 1.0)
            outcome = "ALLOW_CONFIRMED"
            note = "Allowed execution before favorable or stable movement."
        else:
            outcome = "ALLOW_NEUTRAL"
            note = "Allowed execution and market movement stayed neutral."

    else:
        outcome = "UNKNOWN_DECISION"
        note = "Unknown decision type."

    return {
        "execution_outcome": outcome,
        "protection_score": round(protection_score, 6),
        "opportunity_score": round(opportunity_score, 6),
        "outcome_note": note,
    }


def get_entry_price(decision: Dict[str, Any]) -> float:
    """
    Use real market price only.
    Never fall back to stress_score.
    """
    best_ask = fnum(decision.get("best_ask"))
    ticker_last = fnum(decision.get("ticker_last"))
    best_bid = fnum(decision.get("best_bid"))

    if best_ask > 0:
        return best_ask

    if ticker_last > 0:
        return ticker_last

    if best_bid > 0:
        return best_bid

    return 0.0


def validate() -> List[Dict[str, Any]]:
    decisions = load_csv(RISK_GATE)
    snapshots = load_csv(SNAPSHOTS)

    if not decisions:
        raise FileNotFoundError(f"No risk-gate receipts found at {RISK_GATE}")

    if not snapshots:
        raise FileNotFoundError(f"No market snapshots found at {SNAPSHOTS}")

    output = []

    for decision in decisions:
        symbol = decision.get("symbol")
        decision_time = parse_dt(decision.get("receipt_written_at", ""))

        if not symbol or decision_time is None:
            continue

        entry_price = get_entry_price(decision)

        if entry_price <= 0:
            continue

        returns: Dict[str, Optional[float]] = {}
        future_prices: Dict[str, Optional[float]] = {}

        for h in HORIZON_MINUTES:
            future = nearest_future_snapshot(
                snapshots=snapshots,
                symbol=symbol,
                decision_time=decision_time,
                horizon_minutes=h,
            )

            if not future:
                returns[f"return_{h}m_pct"] = None
                future_prices[f"future_price_{h}m"] = None
                continue

            future_price = fnum(future.get("ticker_last"))

            if future_price <= 0:
                returns[f"return_{h}m_pct"] = None
                future_prices[f"future_price_{h}m"] = None
                continue

            ret = ((future_price - entry_price) / entry_price) * 100.0

            returns[f"return_{h}m_pct"] = round(ret, 6)
            future_prices[f"future_price_{h}m"] = future_price

        outcome = classify_outcome(decision.get("risk_decision", ""), returns)

        output.append({
            "decision_time": decision.get("receipt_written_at"),
            "symbol": symbol,
            "risk_decision": decision.get("risk_decision"),
            "regime": decision.get("regime"),
            "guidance": decision.get("guidance"),
            "stress_score": decision.get("stress_score"),
            "entry_price": entry_price,
            **future_prices,
            **returns,
            **outcome,
            "decision_reason": decision.get("decision_reason"),
            "provider_data_hash": decision.get("provider_data_hash"),
        })

    if not output:
        raise RuntimeError(
            "No valid outcome rows were produced. "
            "Check that live_risk_gate_receipts.csv contains best_bid, best_ask, or ticker_last."
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

    return output


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    counts: Dict[str, int] = {}

    for row in rows:
        k = row.get("execution_outcome", "UNKNOWN")
        counts[k] = counts.get(k, 0) + 1

    confirmed = counts.get("PROTECTION_CONFIRMED", 0) + counts.get("ALLOW_CONFIRMED", 0)
    adverse = counts.get("ALLOW_ADVERSE", 0)
    opportunity_cost = counts.get("OPPORTUNITY_COST", 0)
    pending = counts.get("PENDING", 0)

    return {
        "total_outcomes": total,
        "confirmed_outcomes": confirmed,
        "adverse_allows": adverse,
        "opportunity_cost_events": opportunity_cost,
        "pending_outcomes": pending,
        "confirmed_rate": round(confirmed / total, 6) if total else 0.0,
        "outcome_counts": counts,
    }


def main() -> None:
    rows = validate()
    summary = summarize(rows)

    print("EXECUTION OUTCOME VALIDATION COMPLETE")
    print(summary)
    print(f"Wrote outcome validation rows to {OUT}")


if __name__ == "__main__":
    main()
