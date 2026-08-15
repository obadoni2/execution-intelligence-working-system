from __future__ import annotations

import csv
import random
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query


router = APIRouter(prefix="/v1", tags=["SPY Lead Lag Hardening"])

PROBE_PATH = Path("equities/data/spy_probe_output.csv")
THRESHOLD = 1.0


CHANNELS = {
    "spread": "spread_dij",
    "depth": "depth_dij",
    "quote_trade_ratio": "quote_trade_ratio_dij",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def load_rows() -> List[Dict[str, Any]]:
    if not PROBE_PATH.exists():
        return []

    with PROBE_PATH.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def crosses(prev: float, curr: float, threshold: float = THRESHOLD) -> bool:
    return prev < threshold <= curr


def median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def find_crossings(values: List[float]) -> List[int]:
    out = []
    for i in range(1, len(values)):
        if crosses(values[i - 1], values[i]):
            out.append(i)
    return out


def observed_lead_rates(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    composite = [safe_float(r.get("composite_dij")) for r in rows]
    composite_crossings = find_crossings(composite)

    result = {}

    for name, col in CHANNELS.items():
        vals = [safe_float(r.get(col)) for r in rows]
        ch_crossings = find_crossings(vals)

        lead_offsets = []

        for comp_idx in composite_crossings:
            prior = [x for x in ch_crossings if x <= comp_idx]
            if not prior:
                continue

            last_cross = prior[-1]
            lead = comp_idx - last_cross

            if lead > 0:
                lead_offsets.append(lead)

        result[name] = {
            "lead_event_count": len(lead_offsets),
            "lead_rate_given_composite_cross": (
                len(lead_offsets) / len(composite_crossings)
                if composite_crossings
                else 0.0
            ),
            "median_lead_rows": median(lead_offsets),
            "max_lead_rows": max(lead_offsets) if lead_offsets else None,
            "mean_lead_rows": (
                sum(lead_offsets) / len(lead_offsets)
                if lead_offsets
                else None
            ),
        }

    return {
        "composite_crossing_count": len(composite_crossings),
        "channels": result,
    }


def shuffled_null(rows: List[Dict[str, Any]], n_shuffles: int = 200) -> Dict[str, Any]:
    composite = [safe_float(r.get("composite_dij")) for r in rows]
    composite_crossings = find_crossings(composite)

    null_rates = {name: [] for name in CHANNELS}
    null_max_leads = {name: [] for name in CHANNELS}

    for _ in range(n_shuffles):
        for name, col in CHANNELS.items():
            vals = [safe_float(r.get(col)) for r in rows]
            random.shuffle(vals)

            ch_crossings = find_crossings(vals)
            leads = []

            for comp_idx in composite_crossings:
                prior = [x for x in ch_crossings if x <= comp_idx]
                if not prior:
                    continue

                lead = comp_idx - prior[-1]
                if lead > 0:
                    leads.append(lead)

            rate = len(leads) / len(composite_crossings) if composite_crossings else 0.0
            null_rates[name].append(rate)
            null_max_leads[name].append(max(leads) if leads else 0)

    summary = {}

    for name in CHANNELS:
        rates = null_rates[name]
        maxes = null_max_leads[name]

        summary[name] = {
            "null_mean_lead_rate": sum(rates) / len(rates) if rates else 0.0,
            "null_median_lead_rate": median(rates),
            "null_p95_lead_rate": sorted(rates)[int(0.95 * (len(rates) - 1))] if rates else None,
            "null_mean_max_lead": sum(maxes) / len(maxes) if maxes else 0.0,
            "null_p95_max_lead": sorted(maxes)[int(0.95 * (len(maxes) - 1))] if maxes else None,
        }

    return {
        "n_shuffles": n_shuffles,
        "null_summary": summary,
    }


def conditional_forecast(rows: List[Dict[str, Any]], horizon_rows: int = 30) -> Dict[str, Any]:
    composite = [safe_float(r.get("composite_dij")) for r in rows]
    composite_crossings = set(find_crossings(composite))

    result = {}

    for name, col in CHANNELS.items():
        vals = [safe_float(r.get(col)) for r in rows]
        ch_crossings = find_crossings(vals)

        hits = 0
        total = 0
        lead_times = []

        for idx in ch_crossings:
            total += 1

            future_crosses = [
                c for c in composite_crossings
                if idx < c <= idx + horizon_rows
            ]

            if future_crosses:
                hits += 1
                lead_times.append(future_crosses[0] - idx)

        result[name] = {
            "channel_cross_count": total,
            "future_composite_cross_hits": hits,
            "p_composite_stress_given_channel_cross": hits / total if total else 0.0,
            "median_rows_to_composite": median(lead_times),
            "mean_rows_to_composite": (
                sum(lead_times) / len(lead_times)
                if lead_times
                else None
            ),
            "max_rows_to_composite": max(lead_times) if lead_times else None,
        }

    return {
        "horizon_rows": horizon_rows,
        "channels": result,
    }


@router.get("/spy-lead-lag-hardening")
def spy_lead_lag_hardening(
    n_shuffles: int = Query(default=200, ge=10, le=1000),
    horizon_rows: int = Query(default=30, ge=1, le=300),
) -> Dict[str, Any]:
    rows = load_rows()

    if len(rows) < 10:
        return {
            "schema_version": "supt.spy_lead_lag_hardening.v1",
            "error": "not_enough_rows",
            "total_rows": len(rows),
        }

    observed = observed_lead_rates(rows)
    null = shuffled_null(rows, n_shuffles=n_shuffles)
    conditional = conditional_forecast(rows, horizon_rows=horizon_rows)

    comparison = {}

    for name in CHANNELS:
        observed_rate = observed["channels"][name]["lead_rate_given_composite_cross"]
        null_mean = null["null_summary"][name]["null_mean_lead_rate"]

        comparison[name] = {
            "observed_lead_rate": observed_rate,
            "null_mean_lead_rate": null_mean,
            "lead_rate_lift_vs_null": (
                observed_rate / null_mean if null_mean else None
            ),
            "observed_max_lead": observed["channels"][name]["max_lead_rows"],
            "null_p95_max_lead": null["null_summary"][name]["null_p95_max_lead"],
            "max_lead_exceeds_null_p95": (
                observed["channels"][name]["max_lead_rows"]
                > null["null_summary"][name]["null_p95_max_lead"]
                if observed["channels"][name]["max_lead_rows"] is not None
                and null["null_summary"][name]["null_p95_max_lead"] is not None
                else False
            ),
            "p_composite_stress_given_channel_cross": conditional["channels"][name][
                "p_composite_stress_given_channel_cross"
            ],
        }

    return {
        "schema_version": "supt.spy_lead_lag_hardening.v1",
        "source_file": str(PROBE_PATH),
        "threshold": THRESHOLD,
        "total_rows": len(rows),
        "observed": observed,
        "null_distribution": null,
        "conditional_forecast": conditional,
        "comparison": comparison,
        "interpretation": {
            "null_test": "Checks whether observed lead rates exceed shuffled channel-order expectations.",
            "conditional_test": "Checks P(composite stress within horizon | channel crossed).",
            "commercial_question": "Does a channel crossing provide actionable early warning before composite stress forms?",
        },
    }
