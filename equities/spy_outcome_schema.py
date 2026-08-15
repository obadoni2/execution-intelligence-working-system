from __future__ import annotations

SCHEMA_VERSION = "1.0.0"
SCHEMA_FROZEN_AT = "2026-05-12T00:00:00Z"
SCHEMA_HASH = "669974669e50bb604e37288b7b4386632f1306b01f35ba7efb9e295aa1642fe5"

BAD_WINDOW_RULES = {
    "ADVERSE_SELECTION": {
        "metric": "adverse_mid_move_bps_horizon_30s",
        "direction": "above",
        "threshold": 2.0,
    },
    "SPREAD_EXPANSION": {
        "metric": "spread_expansion_ratio_horizon_30s",
        "direction": "above",
        "threshold": 3.0,
    },
    "DEPTH_COLLAPSE": {
        "metric": "depth_collapse_ratio_horizon_30s",
        "direction": "below",
        "threshold": 0.25,
    },
    "QUOTE_TRADE_INSTABILITY": {
        "metric": "quote_to_trade_ratio_horizon_30s",
        "direction": "above",
        "threshold": 50.0,
    },
    "REALIZED_SPREAD_DETERIORATION": {
        "metric": "realized_spread_bps_horizon_30s",
        "direction": "above",
        "threshold": 1.5,
    },
    "DEGRADED_EXECUTION_PROXY": {
        "metric": "effective_cost_vs_mid_bps_horizon_30s",
        "direction": "above",
        "threshold": 2.5,
    },
}


def is_bad_window(metrics: dict) -> tuple[bool, list[str]]:
    triggered = []

    for name, rule in BAD_WINDOW_RULES.items():
        metric = rule["metric"]

        if metric not in metrics or metrics[metric] is None:
            triggered.append(f"MISSING:{name}")
            continue

        value = float(metrics[metric])

        if rule["direction"] == "above" and value > rule["threshold"]:
            triggered.append(name)

        if rule["direction"] == "below" and value < rule["threshold"]:
            triggered.append(name)

    actual = [x for x in triggered if not x.startswith("MISSING:")]
    return len(actual) > 0, triggered


if __name__ == "__main__":
    print("SPY outcome schema frozen")
    print(f"Version: {SCHEMA_VERSION}")
    print(f"Frozen at: {SCHEMA_FROZEN_AT}")
    print(f"Hash: {SCHEMA_HASH}")
