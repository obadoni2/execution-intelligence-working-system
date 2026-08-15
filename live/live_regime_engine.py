from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


IN = Path("live/data/gateio_market_snapshots.csv")
OUT = Path("live/data/live_stress_receipts.csv")


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def regime_and_guidance(row: Dict[str, Any]) -> Dict[str, Any]:
    spread_bps = fnum(row.get("spread_bps"))
    depth = fnum(row.get("top_depth"))
    trade_count = fnum(row.get("trade_count_100"))
    buy = fnum(row.get("buy_trades_100"))
    sell = fnum(row.get("sell_trades_100"))

    imbalance = abs(buy - sell) / max(trade_count, 1.0)

    spread_score = min(spread_bps / 10.0, 1.0)
    depth_score = 1.0 if depth <= 1 else min(1.0 / depth, 1.0)
    imbalance_score = min(imbalance, 1.0)

    stress_score = round(
        (0.45 * spread_score) +
        (0.30 * depth_score) +
        (0.25 * imbalance_score),
        6,
    )

    if stress_score >= 0.75:
        regime = "CRITICAL"
        guidance = "BLOCK"
    elif stress_score >= 0.50:
        regime = "HIGH_STRESS"
        guidance = "PAUSE"
    elif stress_score >= 0.25:
        regime = "CAUTION"
        guidance = "REDUCE_SIZE"
    else:
        regime = "NORMAL"
        guidance = "EXECUTE"

    return {
        "stress_score": stress_score,
        "spread_score": round(spread_score, 6),
        "depth_score": round(depth_score, 6),
        "imbalance_score": round(imbalance_score, 6),
        "trade_imbalance": round(imbalance, 6),
        "regime": regime,
        "guidance": guidance,
    }


def load_rows() -> List[Dict[str, Any]]:
    if not IN.exists():
        return []
    with IN.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_by_symbol(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest = {}
    for row in rows:
        latest[row["symbol"]] = row
    return list(latest.values())


def main() -> None:
    rows = load_rows()
    if not rows:
        raise FileNotFoundError(f"No live snapshots found at {IN}")

    receipts = []
    now = datetime.now(timezone.utc).isoformat()

    for row in latest_by_symbol(rows):
        scores = regime_and_guidance(row)

        receipts.append({
            "receipt_written_at": now,
            "source_timestamp_utc": row.get("timestamp_utc"),
            "exchange": row.get("exchange"),
            "symbol": row.get("symbol"),
            "best_bid": row.get("best_bid"),
            "best_ask": row.get("best_ask"),
            "spread_bps": row.get("spread_bps"),
            "top_depth": row.get("top_depth"),
            "trade_count_100": row.get("trade_count_100"),
            "buy_trades_100": row.get("buy_trades_100"),
            "sell_trades_100": row.get("sell_trades_100"),
            "ticker_last": row.get("ticker_last"),
            "provider_data_hash": row.get("provider_data_hash"),
            **scores,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(receipts[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(receipts)

    print(f"Wrote {len(receipts)} live stress receipts to {OUT}")

    for r in receipts:
        print(
            f"{r['symbol']}: {r['regime']} | {r['guidance']} | "
            f"score={r['stress_score']} spread={r['spread_bps']}bps"
        )


if __name__ == "__main__":
    main()
