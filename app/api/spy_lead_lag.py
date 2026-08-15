from __future__ import annotations

import csv
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter


router = APIRouter(prefix="/v1", tags=["SPY Lead Lag"])

PROBE_PATH = Path("equities/data/spy_probe_output.csv")

THRESHOLD = 1.0


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def load_probe_rows() -> List[Dict[str, Any]]:
    if not PROBE_PATH.exists():
        return []

    with PROBE_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def crossed(prev: float, current: float, threshold: float = THRESHOLD) -> bool:
    return prev < threshold <= current


def median(values: List[int]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


@router.get("/spy-lead-lag")
def spy_lead_lag() -> Dict[str, Any]:
    rows = load_probe_rows()

    if len(rows) < 2:
        return {
            "schema_version": "supt.spy_lead_lag.v1",
            "source_file": str(PROBE_PATH),
            "error": "not_enough_rows",
            "total_rows": len(rows),
        }

    channel_names = {
        "spread_dij": "spread",
        "depth_dij": "depth",
        "quote_trade_ratio_dij": "quote_trade_ratio",
    }

    composite_crossings = []

    for i in range(1, len(rows)):
        prev_composite = safe_float(rows[i - 1].get("composite_dij"))
        curr_composite = safe_float(rows[i].get("composite_dij"))

        if crossed(prev_composite, curr_composite):
            composite_crossings.append(i)

    channel_leads: Dict[str, List[int]] = {
        "spread": [],
        "depth": [],
        "quote_trade_ratio": [],
    }

    transition_events = []

    for composite_idx in composite_crossings:
        event = {
            "composite_cross_index": composite_idx,
            "timestamp": rows[composite_idx].get("timestamp"),
            "composite_dij": safe_float(rows[composite_idx].get("composite_dij")),
            "channel_leads": {},
            "leading_channel": None,
            "max_lead_rows": 0,
        }

        best_channel = None
        best_lead = 0

        for column, name in channel_names.items():
            channel_cross_idx = None

            for j in range(composite_idx, 0, -1):
                prev_val = safe_float(rows[j - 1].get(column))
                curr_val = safe_float(rows[j].get(column))

                if crossed(prev_val, curr_val):
                    channel_cross_idx = j
                    break

            if channel_cross_idx is None:
                lead = 0
            else:
                lead = composite_idx - channel_cross_idx

            event["channel_leads"][name] = {
                "lead_rows": lead,
                "cross_index": channel_cross_idx,
                "cross_timestamp": (
                    rows[channel_cross_idx].get("timestamp")
                    if channel_cross_idx is not None
                    else None
                ),
                "cross_dij": (
                    safe_float(rows[channel_cross_idx].get(column))
                    if channel_cross_idx is not None
                    else None
                ),
            }

            if lead > 0:
                channel_leads[name].append(lead)

            if lead > best_lead:
                best_lead = lead
                best_channel = name

        event["leading_channel"] = best_channel
        event["max_lead_rows"] = best_lead
        transition_events.append(event)

    lead_summary = {}

    for channel, leads in channel_leads.items():
        lead_summary[channel] = {
            "lead_event_count": len(leads),
            "median_lead_rows": median(leads),
            "mean_lead_rows": (sum(leads) / len(leads)) if leads else None,
            "max_lead_rows": max(leads) if leads else None,
        }

    leading_counts = {}
    for event in transition_events:
        ch = event.get("leading_channel")
        if ch:
            leading_counts[ch] = leading_counts.get(ch, 0) + 1

    return {
        "schema_version": "supt.spy_lead_lag.v1",
        "source_file": str(PROBE_PATH),
        "threshold": THRESHOLD,
        "total_rows": len(rows),
        "composite_crossing_count": len(composite_crossings),
        "lead_summary": lead_summary,
        "leading_channel_counts": leading_counts,
        "events": transition_events[-50:],
        "interpretation": {
            "purpose": "Detect whether individual SPY channels cross stress threshold before composite_dij.",
            "note": "Positive lead_rows means the channel crossed before the composite crossing.",
        },
    }
