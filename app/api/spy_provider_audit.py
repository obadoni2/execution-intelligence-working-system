from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query


router = APIRouter(prefix="/v1", tags=["SPY Provider Audit"])

PROBE_PATH = Path("equities/data/spy_probe_output.csv")
NORMALIZED_PATH = Path("equities/data/provider/spy_provider_normalized.csv")
RECEIPTS_PATH = Path("equities/data/spy_outcomes.csv")


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    if path == RECEIPTS_PATH:
        with path.open("r", encoding="utf-8") as f:
            clean_lines = [line for line in f if not line.startswith("#")]
        return list(csv.DictReader(clean_lines))

    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@router.get("/spy-provider-audit")
def spy_provider_audit(limit: int = Query(default=25, ge=1, le=500)) -> Dict[str, Any]:
    provider_rows = load_csv(NORMALIZED_PATH)
    probe_rows = load_csv(PROBE_PATH)
    receipt_rows = load_csv(RECEIPTS_PATH)

    probe_by_ts = {r.get("timestamp"): r for r in probe_rows}
    receipt_by_ts = {r.get("bar_open_utc"): r for r in receipt_rows}

    providers = {}

    for row in provider_rows[-limit:]:
        ts = row.get("timestamp")
        provider = row.get("provider", "unknown")
        provider_hash = row.get("provider_data_hash", "")

        probe = probe_by_ts.get(ts, {})
        receipt = receipt_by_ts.get(ts, {})

        providers.setdefault(
            provider,
            {
                "provider": provider,
                "provider_data_hashes": set(),
                "windows": [],
            },
        )

        providers[provider]["provider_data_hashes"].add(provider_hash)

        spread = max(float(row.get("ask", 0.0)) - float(row.get("bid", 0.0)), 0.0)
        depth = float(row.get("bid_size", 0.0)) + float(row.get("ask_size", 0.0))
        trade_updates = max(float(row.get("trade_updates", 0.0)), 1e-9)
        quote_trade_ratio = float(row.get("quote_updates", 0.0)) / trade_updates

        providers[provider]["windows"].append(
            {
                "timestamp": ts,
                "raw_ordered_positive_sequence": {
                    "spread": spread,
                    "depth": depth,
                    "quote_trade_ratio": quote_trade_ratio,
                },
                "probe_output": {
                    "spread_dij": probe.get("spread_dij"),
                    "depth_dij": probe.get("depth_dij"),
                    "quote_trade_ratio_dij": probe.get("quote_trade_ratio_dij"),
                    "composite_dij": probe.get("composite_dij"),
                    "regime": probe.get("regime"),
                },
                "receipt_output": {
                    "decision_state": receipt.get("decision_state"),
                    "is_bad": receipt.get("is_bad"),
                    "triggered_rules": receipt.get("triggered_rules"),
                    "schema_hash": receipt.get("schema_hash"),
                    "provider_data_hash": receipt.get("provider_data_hash"),
                },
            }
        )

    result = []
    for item in providers.values():
        item["provider_data_hashes"] = sorted(item["provider_data_hashes"])
        result.append(item)

    return {
        "schema_version": "supt.spy_provider_audit.v1",
        "normalized_source": str(NORMALIZED_PATH),
        "probe_source": str(PROBE_PATH),
        "receipt_source": str(RECEIPTS_PATH),
        "limit": limit,
        "providers": result,
    }
