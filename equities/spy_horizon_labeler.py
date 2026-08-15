from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


NORMALIZED_PATH = Path("equities/data/provider/spy_provider_normalized.csv")
LABELS_PATH = Path("equities/data/validation/spy_horizon_labels.csv")

HORIZON_SECONDS = 30


FIELDS = [
    "timestamp",
    "horizon_end_utc",
    "adverse_mid_move_bps_horizon_30s",
    "spread_expansion_ratio_horizon_30s",
    "depth_collapse_ratio_horizon_30s",
    "quote_to_trade_ratio_horizon_30s",
    "realized_spread_bps_horizon_30s",
    "effective_cost_vs_mid_bps_horizon_30s",
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


def parse_dt(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def mid(row: Dict[str, Any]) -> float:
    return (safe_float(row.get("bid")) + safe_float(row.get("ask"))) / 2.0


def spread(row: Dict[str, Any]) -> float:
    return max(safe_float(row.get("ask")) - safe_float(row.get("bid")), 0.0)


def depth(row: Dict[str, Any]) -> float:
    return safe_float(row.get("bid_size")) + safe_float(row.get("ask_size"))


def bps(value: float) -> float:
    return value * 10000.0


def load_rows() -> List[Dict[str, Any]]:
    if not NORMALIZED_PATH.exists():
        raise FileNotFoundError("Run spy_provider_adapter.py first.")

    with NORMALIZED_PATH.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows.sort(key=lambda r: parse_dt(r["timestamp"]))
    return rows


def trailing_median(values: List[float]) -> float:
    if not values:
        return 0.0

    s = sorted(values)
    n = len(s)
    mid_idx = n // 2

    if n % 2 == 1:
        return s[mid_idx]

    return (s[mid_idx - 1] + s[mid_idx]) / 2.0


def label_rows() -> List[Dict[str, Any]]:
    rows = load_rows()
    output: List[Dict[str, Any]] = []

    all_spreads: List[float] = []
    all_depths: List[float] = []

    parsed = [(parse_dt(r["timestamp"]), r) for r in rows]

    for idx, (ts, row) in enumerate(parsed):
        current_mid = mid(row)
        current_spread = spread(row)
        current_depth = depth(row)

        trailing_spreads = all_spreads[-1800:]
        trailing_depths = all_depths[-1800:]

        spread_med = trailing_median(trailing_spreads) or current_spread or 1e-9
        depth_med = trailing_median(trailing_depths) or current_depth or 1e-9

        horizon_end = ts + timedelta(seconds=HORIZON_SECONDS)
        future = [r for t, r in parsed[idx + 1 :] if t <= horizon_end]

        if not future:
            all_spreads.append(current_spread)
            all_depths.append(current_depth)
            continue

        future_mids = [mid(r) for r in future]
        future_spreads = [spread(r) for r in future]
        future_depths = [depth(r) for r in future]

        end_mid = future_mids[-1]
        adverse_mid_move = abs(end_mid - current_mid) / max(current_mid, 1e-9)
        adverse_mid_move_bps = bps(adverse_mid_move)

        max_spread = max(future_spreads) if future_spreads else current_spread
        min_depth = min(future_depths) if future_depths else current_depth

        spread_expansion_ratio = max_spread / max(spread_med, 1e-9)
        depth_collapse_ratio = min_depth / max(depth_med, 1e-9)

        quote_updates = sum(safe_float(r.get("quote_updates")) for r in future)
        trade_updates = sum(safe_float(r.get("trade_updates")) for r in future)
        quote_to_trade_ratio = quote_updates / max(trade_updates, 1e-9)

        realized_spread_bps = bps(max_spread / max(current_mid, 1e-9))
        effective_cost_bps = bps(current_spread / max(current_mid, 1e-9))

        output.append(
            {
                "timestamp": row["timestamp"],
                "horizon_end_utc": horizon_end.isoformat(),
                "adverse_mid_move_bps_horizon_30s": round(adverse_mid_move_bps, 6),
                "spread_expansion_ratio_horizon_30s": round(spread_expansion_ratio, 6),
                "depth_collapse_ratio_horizon_30s": round(depth_collapse_ratio, 6),
                "quote_to_trade_ratio_horizon_30s": round(quote_to_trade_ratio, 6),
                "realized_spread_bps_horizon_30s": round(realized_spread_bps, 6),
                "effective_cost_vs_mid_bps_horizon_30s": round(effective_cost_bps, 6),
                "provider": row.get("provider", "local_csv"),
                "provider_data_hash": row.get("provider_data_hash", ""),
            }
        )

        all_spreads.append(current_spread)
        all_depths.append(current_depth)

    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LABELS_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)

    return output


def main() -> None:
    rows = label_rows()
    print(f"Wrote {len(rows)} SPY horizon labels to {LABELS_PATH}")


if __name__ == "__main__":
    main()
