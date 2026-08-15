from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


STRESS = Path("live/data/live_stress_receipts.csv")
ALERTS = Path("live/data/live_alerts.csv")
OUT = Path("live/data/live_risk_gate_receipts.csv")
KILL = Path("live/data/KILL_SWITCH_ON")

ALLOWED_SYMBOLS = {
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "TON/USDT",
}

MIN_DEPTH = 1.0
MAX_SPREAD_BPS_ALLOW = 5.0
MAX_SPREAD_BPS_REDUCE = 10.0
MAX_ALERT_CONFIDENCE_ALLOW = 0.70


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for row in rows:
        out[row.get("symbol", "")] = row
    return out


def latest_alerts_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for row in rows:
        out[row.get("symbol", "")] = row
    return out


def risk_gate_decision(stress: Dict[str, Any], alert: Dict[str, Any] | None) -> Dict[str, Any]:
    symbol = stress.get("symbol", "")
    regime = stress.get("regime", "UNKNOWN")
    guidance = stress.get("guidance", "UNKNOWN")
    spread_bps = fnum(stress.get("spread_bps"))
    depth = fnum(stress.get("top_depth"))
    stress_score = fnum(stress.get("stress_score"))
    alert_conf = fnum(alert.get("confidence")) if alert else 0.0
    alert_text = alert.get("alerts", "") if alert else ""

    reasons = []

    if KILL.exists():
        return {
            "risk_decision": "BLOCK",
            "max_size_multiplier": 0.0,
            "decision_reason": "KILL_SWITCH_ON",
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if symbol not in ALLOWED_SYMBOLS:
        return {
            "risk_decision": "BLOCK",
            "max_size_multiplier": 0.0,
            "decision_reason": "SYMBOL_NOT_ALLOWED",
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if regime == "CRITICAL":
        reasons.append("CRITICAL_REGIME")
        return {
            "risk_decision": "BLOCK",
            "max_size_multiplier": 0.0,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if regime == "HIGH_STRESS" or guidance in {"PAUSE", "BLOCK"}:
        reasons.append("HIGH_STRESS_OR_PAUSE_GUIDANCE")
        return {
            "risk_decision": "PAUSE",
            "max_size_multiplier": 0.0,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if depth < MIN_DEPTH:
        reasons.append("LOW_DEPTH")

    if spread_bps > MAX_SPREAD_BPS_REDUCE:
        reasons.append("SPREAD_TOO_WIDE")
        return {
            "risk_decision": "PAUSE",
            "max_size_multiplier": 0.0,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if regime == "CAUTION" or guidance == "REDUCE_SIZE":
        reasons.append("CAUTION_OR_REDUCE_SIZE_GUIDANCE")
        return {
            "risk_decision": "REDUCE_SIZE",
            "max_size_multiplier": 0.25,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if spread_bps > MAX_SPREAD_BPS_ALLOW:
        reasons.append("MODERATE_SPREAD")
        return {
            "risk_decision": "REDUCE_SIZE",
            "max_size_multiplier": 0.50,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if alert_conf > MAX_ALERT_CONFIDENCE_ALLOW:
        reasons.append("HIGH_CONFIDENCE_ALERT")
        return {
            "risk_decision": "REDUCE_SIZE",
            "max_size_multiplier": 0.50,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    if stress_score >= 0.25:
        reasons.append("ELEVATED_STRESS_SCORE")
        return {
            "risk_decision": "REDUCE_SIZE",
            "max_size_multiplier": 0.50,
            "decision_reason": ",".join(reasons),
            "alert_confidence": alert_conf,
            "alert_text": alert_text,
        }

    reasons.append("CONDITIONS_ACCEPTABLE")
    return {
        "risk_decision": "ALLOW",
        "max_size_multiplier": 1.0,
        "decision_reason": ",".join(reasons),
        "alert_confidence": alert_conf,
        "alert_text": alert_text,
    }


def main() -> None:
    stress_rows = load_csv(STRESS)
    alert_rows = load_csv(ALERTS)

    if not stress_rows:
        raise FileNotFoundError(f"No stress receipts found at {STRESS}")

    latest_stress = latest_by_symbol(stress_rows)
    latest_alerts = latest_alerts_by_symbol(alert_rows)

    now = datetime.now(timezone.utc).isoformat()
    receipts = []

    for symbol, stress in latest_stress.items():
        alert = latest_alerts.get(symbol)
        decision = risk_gate_decision(stress, alert)

        receipts.append({
            "receipt_written_at": now,
            "symbol": symbol,
            "regime": stress.get("regime"),
            "guidance": stress.get("guidance"),
            "stress_score": stress.get("stress_score"),
            "spread_bps": stress.get("spread_bps"),
            "top_depth": stress.get("top_depth"),
            "trade_imbalance": stress.get("trade_imbalance"),
            "best_bid": stress.get("best_bid"),
            "best_ask": stress.get("best_ask"),
            "ticker_last": stress.get("ticker_last"),
            "provider_data_hash": stress.get("provider_data_hash"),
            "kill_switch_on": str(KILL.exists()).upper(),
            **decision,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(receipts[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(receipts)

    print(f"Wrote {len(receipts)} live risk-gate receipts to {OUT}")

    for r in receipts:
        print(
            f"{r['symbol']}: {r['risk_decision']} "
            f"size={r['max_size_multiplier']} reason={r['decision_reason']}"
        )


if __name__ == "__main__":
    main()
