from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ORCH = Path("live/data/execution_orchestrator_receipts.csv")
RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/paper_trading_receipts.csv")

STARTING_BALANCE = 10_000.0
TRADE_NOTIONAL = 100.0
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005


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


def get_price(risk: Dict[str, Any]) -> float:
    ticker = fnum(risk.get("ticker_last"))
    bid = fnum(risk.get("best_bid"))
    ask = fnum(risk.get("best_ask"))

    if ticker > 0:
        return ticker
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    if ask > 0:
        return ask
    if bid > 0:
        return bid

    return 0.0


def simulate_trade(orch: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
    symbol = orch.get("symbol")
    route = orch.get("execution_route")
    action = orch.get("orchestrator_action")
    risk_decision = orch.get("risk_decision")

    price = get_price(risk)

    if route != "PAPER":
        return {
            "trade_id": f"NO_TRADE_{uuid.uuid4().hex[:10]}",
            "symbol": symbol,
            "paper_action": "NO_TRADE",
            "reason": orch.get("reason"),
            "execution_route": route,
            "entry_price": price,
            "notional": 0.0,
            "quantity": 0.0,
            "fee": 0.0,
            "slippage_cost": 0.0,
            "simulated_cash_change": 0.0,
            "status": "SKIPPED",
        }

    if price <= 0:
        return {
            "trade_id": f"FAILED_{uuid.uuid4().hex[:10]}",
            "symbol": symbol,
            "paper_action": "NO_TRADE",
            "reason": "NO_VALID_PRICE",
            "execution_route": route,
            "entry_price": price,
            "notional": 0.0,
            "quantity": 0.0,
            "fee": 0.0,
            "slippage_cost": 0.0,
            "simulated_cash_change": 0.0,
            "status": "FAILED",
        }

    multiplier = fnum(orch.get("max_size_multiplier"), 1.0)
    notional = TRADE_NOTIONAL * multiplier

    fee = notional * FEE_RATE
    slippage = notional * SLIPPAGE_RATE
    quantity = notional / price

    paper_action = "SIMULATED_BUY"

    if risk_decision == "REDUCE_SIZE":
        paper_action = "SIMULATED_REDUCED_BUY"

    return {
        "trade_id": f"PAPER_{uuid.uuid4().hex[:10]}",
        "symbol": symbol,
        "paper_action": paper_action,
        "reason": orch.get("reason"),
        "execution_route": route,
        "entry_price": round(price, 8),
        "notional": round(notional, 6),
        "quantity": round(quantity, 8),
        "fee": round(fee, 6),
        "slippage_cost": round(slippage, 6),
        "simulated_cash_change": round(-(notional + fee + slippage), 6),
        "status": "OPEN_SIMULATED",
    }


def main() -> None:
    orch_rows = load_csv(ORCH)
    risk_rows = load_csv(RISK_GATE)

    if not orch_rows:
        raise FileNotFoundError(f"No orchestrator receipts found at {ORCH}")

    if not risk_rows:
        raise FileNotFoundError(f"No risk gate receipts found at {RISK_GATE}")

    latest_orch = latest_by_symbol(orch_rows)
    latest_risk = latest_by_symbol(risk_rows)

    now = datetime.now(timezone.utc).isoformat()
    receipts = []

    for symbol, orch in latest_orch.items():
        risk = latest_risk.get(symbol, {})
        trade = simulate_trade(orch, risk)

        receipts.append({
            "receipt_written_at": now,
            "starting_balance": STARTING_BALANCE,
            "symbol": symbol,
            "orchestrator_action": orch.get("orchestrator_action"),
            "risk_decision": orch.get("risk_decision"),
            "policy_stage": orch.get("policy_stage"),
            "approval_status": orch.get("approval_status"),
            "policy_trust_label": orch.get("policy_trust_label"),
            "policy_trust_score": orch.get("policy_trust_score"),
            **trade,
            "provider_data_hash": orch.get("provider_data_hash"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(receipts[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(receipts)

    executed = sum(1 for r in receipts if r["status"] == "OPEN_SIMULATED")
    skipped = sum(1 for r in receipts if r["status"] == "SKIPPED")

    print("PAPER TRADING ENGINE COMPLETE")
    print(f"Simulated trades: {executed}")
    print(f"Skipped: {skipped}")
    print(f"Wrote {len(receipts)} paper trading receipts to {OUT}")

    for r in receipts:
        print(
            f"{r['symbol']}: {r['paper_action']} "
            f"status={r['status']} route={r['execution_route']} "
            f"notional={r['notional']}"
        )


if __name__ == "__main__":
    main()
