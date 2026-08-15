from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Dict, List


RAW_PATH = Path("equities/data/provider/spy_provider_raw.csv")
NORMALIZED_PATH = Path("equities/data/provider/spy_provider_normalized.csv")


FIELDS = [
    "timestamp",
    "symbol",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "quote_updates",
    "trade_updates",
    "last_price",
    "volume",
    "provider",
    "provider_data_hash",
]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_provider_rows() -> List[Dict[str, Any]]:
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Missing {RAW_PATH}. Add provider CSV with columns: "
            "timestamp,symbol,bid,ask,bid_size,ask_size,quote_updates,trade_updates,last_price,volume"
        )

    provider_hash = file_sha256(RAW_PATH)

    with RAW_PATH.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    output: List[Dict[str, Any]] = []

    for row in rows:
        output.append(
            {
                "timestamp": row.get("timestamp"),
                "symbol": row.get("symbol", "SPY"),
                "bid": safe_float(row.get("bid")),
                "ask": safe_float(row.get("ask")),
                "bid_size": safe_float(row.get("bid_size")),
                "ask_size": safe_float(row.get("ask_size")),
                "quote_updates": safe_float(row.get("quote_updates")),
                "trade_updates": safe_float(row.get("trade_updates")),
                "last_price": safe_float(row.get("last_price")),
                "volume": safe_float(row.get("volume")),
                "provider": row.get("provider", "local_csv"),
                "provider_data_hash": provider_hash,
            }
        )

    NORMALIZED_PATH.parent.mkdir(parents=True, exist_ok=True)

    with NORMALIZED_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)

    return output


def main() -> None:
    rows = normalize_provider_rows()
    print(f"Normalized {len(rows)} SPY provider rows to {NORMALIZED_PATH}")
    if rows:
        print(f"Provider data hash: {rows[0]['provider_data_hash']}")


if __name__ == "__main__":
    main()
