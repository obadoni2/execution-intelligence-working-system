from __future__ import annotations

import csv, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import ccxt

OUT = Path("live/data/gateio_market_snapshots.csv")

SYMBOLS = [
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
]


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except Exception:
        return default


def row_hash(row: Dict[str, Any]) -> str:
    raw = "|".join(str(row[k]) for k in sorted(row.keys()))
    return hashlib.sha256(raw.encode()).hexdigest()


def collect_symbol(exchange, symbol: str) -> Dict[str, Any]:
    ob = exchange.fetch_order_book(symbol, limit=20)
    trades = exchange.fetch_trades(symbol, limit=100)
    ticker = exchange.fetch_ticker(symbol)

    bid = safe_float(ob["bids"][0][0]) if ob.get("bids") else 0.0
    ask = safe_float(ob["asks"][0][0]) if ob.get("asks") else 0.0
    bid_size = safe_float(ob["bids"][0][1]) if ob.get("bids") else 0.0
    ask_size = safe_float(ob["asks"][0][1]) if ob.get("asks") else 0.0

    mid = (bid + ask) / 2 if bid and ask else 0.0
    spread = max(ask - bid, 0.0)
    spread_bps = (spread / mid * 10000) if mid else 0.0

    buy_trades = sum(1 for t in trades if t.get("side") == "buy")
    sell_trades = sum(1 for t in trades if t.get("side") == "sell")

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exchange": "gateio",
        "symbol": symbol,
        "best_bid": bid,
        "best_ask": ask,
        "spread": spread,
        "spread_bps": round(spread_bps, 8),
        "top_depth": bid_size + ask_size,
        "trade_count_100": len(trades),
        "buy_trades_100": buy_trades,
        "sell_trades_100": sell_trades,
        "ticker_last": safe_float(ticker.get("last")),
        "ticker_volume": safe_float(ticker.get("baseVolume")),
        "percentage_change": safe_float(ticker.get("percentage")),
    }

    row["provider_data_hash"] = row_hash(row)
    return row


def append_rows(rows):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    exchange = ccxt.gateio({"enableRateLimit": True})
    rows = []

    for symbol in SYMBOLS:
        try:
            row = collect_symbol(exchange, symbol)
            rows.append(row)
            print(f"{symbol}: last={row['ticker_last']} spread_bps={row['spread_bps']}")
        except Exception as e:
            print(f"Failed {symbol}: {e}")

    if rows:
        append_rows(rows)
        print(f"Wrote {len(rows)} live market snapshots to {OUT}")


if __name__ == "__main__":
    main()
