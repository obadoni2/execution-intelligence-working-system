from __future__ import annotations

import csv
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PAPER = Path("live/data/paper_trading_receipts.csv")
RISK = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/realistic_execution_simulation.csv")

BASE_LATENCY_MS = 250
MAX_LATENCY_MS = 2500
BASE_FEE_RATE = 0.001
BASE_SLIPPAGE_BPS = 5.0


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


def latency_model(stress_score: float, spread_bps: float) -> int:
    stress_factor = min(max(stress_score, 0.0), 1.0)
    spread_factor = min(spread_bps / 10.0, 1.0)
    jitter = random.randint(0, 300)

    latency = BASE_LATENCY_MS + int(1000 * stress_factor) + int(700 * spread_factor) + jitter
    return min(latency, MAX_LATENCY_MS)


def slippage_model(spread_bps: float, stress_score: float, liquidity_depth: float) -> float:
    liquidity_penalty = 0.0
    if liquidity_depth <= 0:
        liquidity_penalty = 20.0
    elif liquidity_depth < 1:
        liquidity_penalty = 10.0
    elif liquidity_depth < 10:
        liquidity_penalty = 4.0

    return round(BASE_SLIPPAGE_BPS + spread_bps * 0.5 + stress_score * 15.0 + liquidity_penalty, 6)


def fill_model(notional: float, top_depth: float, stress_score: float) -> Dict[str, Any]:
    if notional <= 0:
        return {
            "fill_status": "NO_ORDER",
            "fill_ratio": 0.0,
            "filled_notional": 0.0,
        }

    if top_depth <= 0:
        return {
            "fill_status": "REJECTED_NO_LIQUIDITY",
            "fill_ratio": 0.0,
            "filled_notional": 0.0,
        }

    available_capacity = top_depth * 10.0
    base_ratio = min(1.0, available_capacity / notional)

    stress_penalty = min(stress_score * 0.25, 0.25)
    fill_ratio = max(0.0, base_ratio - stress_penalty)

    if fill_ratio >= 0.95:
        status = "FULL_FILL"
    elif fill_ratio > 0:
        status = "PARTIAL_FILL"
    else:
        status = "REJECTED"

    return {
        "fill_status": status,
        "fill_ratio": round(fill_ratio, 6),
        "filled_notional": round(notional * fill_ratio, 6),
    }


def simulate(row: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
    symbol = row.get("symbol")
    notional = fnum(row.get("notional"))
    entry_price = fnum(row.get("entry_price"))

    stress_score = fnum(risk.get("stress_score"))
    spread_bps = fnum(risk.get("spread_bps"))
    top_depth = fnum(risk.get("top_depth"))

    latency_ms = latency_model(stress_score, spread_bps)
    slippage_bps = slippage_model(spread_bps, stress_score, top_depth)

    fill = fill_model(notional, top_depth, stress_score)

    filled_notional = fnum(fill.get("filled_notional"))
    fee = filled_notional * BASE_FEE_RATE
    slippage_cost = filled_notional * (slippage_bps / 10000.0)

    adjusted_entry_price = entry_price * (1 + slippage_bps / 10000.0) if entry_price > 0 else 0.0

    total_execution_cost = fee + slippage_cost

    if row.get("status") != "OPEN_SIMULATED":
        execution_status = "SKIPPED"
    elif fill["fill_status"] in {"REJECTED", "REJECTED_NO_LIQUIDITY"}:
        execution_status = "FAILED_REALISTIC_EXECUTION"
    elif fill["fill_status"] == "PARTIAL_FILL":
        execution_status = "PARTIAL_REALISTIC_EXECUTION"
    else:
        execution_status = "FILLED_REALISTIC_EXECUTION"

    return {
        "receipt_written_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "paper_trade_id": row.get("trade_id"),
        "paper_status": row.get("status"),
        "paper_action": row.get("paper_action"),
        "policy_stage": row.get("policy_stage"),
        "policy_trust_label": row.get("policy_trust_label"),
        "entry_price": round(entry_price, 8),
        "adjusted_entry_price": round(adjusted_entry_price, 8),
        "requested_notional": round(notional, 6),
        "filled_notional": round(filled_notional, 6),
        "fill_ratio": fill.get("fill_ratio"),
        "fill_status": fill.get("fill_status"),
        "latency_ms": latency_ms,
        "spread_bps": round(spread_bps, 6),
        "stress_score": round(stress_score, 6),
        "top_depth": round(top_depth, 6),
        "slippage_bps": slippage_bps,
        "fee": round(fee, 6),
        "slippage_cost": round(slippage_cost, 6),
        "total_execution_cost": round(total_execution_cost, 6),
        "execution_status": execution_status,
        "reason": row.get("reason"),
        "provider_data_hash": row.get("provider_data_hash"),
    }


def main() -> None:
    paper_rows = load_csv(PAPER)
    risk_rows = load_csv(RISK)

    if not paper_rows:
        raise FileNotFoundError(f"No paper trading receipts found at {PAPER}")

    if not risk_rows:
        raise FileNotFoundError(f"No risk gate receipts found at {RISK}")

    latest_paper = latest_by_symbol(paper_rows)
    latest_risk = latest_by_symbol(risk_rows)

    outputs = []
    for symbol, paper in latest_paper.items():
        risk = latest_risk.get(symbol, {})
        outputs.append(simulate(paper, risk))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outputs[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(outputs)

    print("REALISTIC EXECUTION SIMULATION COMPLETE")
    print(f"Wrote {len(outputs)} realistic execution rows to {OUT}")

    for r in outputs:
        print(
            f"{r['symbol']}: {r['execution_status']} "
            f"fill={r['fill_status']} ratio={r['fill_ratio']} "
            f"latency={r['latency_ms']}ms cost={r['total_execution_cost']}"
        )


if __name__ == "__main__":
    main()
