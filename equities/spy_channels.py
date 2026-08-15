from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def load_spy_rows(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)

    if not p.exists():
        return []

    with p.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_channels(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output = []

    for row in rows:
        bid = safe_float(row.get("bid"))
        ask = safe_float(row.get("ask"))
        bid_size = safe_float(row.get("bid_size"))
        ask_size = safe_float(row.get("ask_size"))
        quote_updates = safe_float(row.get("quote_updates"))
        trade_updates = safe_float(row.get("trade_updates"))

        spread = max(ask - bid, 0.0)
        depth = bid_size + ask_size

        quote_trade_ratio = (
            quote_updates / trade_updates
            if trade_updates > 0
            else quote_updates
        )

        output.append(
            {
                "timestamp": row.get("timestamp"),
                "symbol": row.get("symbol", "SPY"),
                "spread": spread,
                "depth": depth,
                "quote_trade_ratio": quote_trade_ratio,
                "last_price": safe_float(row.get("last_price")),
                "volume": safe_float(row.get("volume")),
            }
        )

    return output
