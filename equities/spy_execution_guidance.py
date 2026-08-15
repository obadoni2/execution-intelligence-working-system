from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


INPUT_CSV = Path("equities/data/spy_probe_output.csv")
OUTPUT_JSON = Path("equities/data/spy_execution_guidance.json")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def load_rows() -> List[Dict[str, Any]]:
    if not INPUT_CSV.exists():
        return []
    with INPUT_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def classify_action(composite: float, spread: float, depth: float, qtu: float, divergence: float) -> Dict[str, Any]:
    if composite >= 1.25 or spread >= 1.5 or qtu >= 1.5:
        return {
            "risk_state": "HIGH_STRESS",
            "recommended_action": "PAUSE",
            "can_execute_now": False,
            "max_position_multiplier": 0.0,
            "operator_guidance": "Pause non-urgent SPY execution. Microstructure stress is elevated.",
        }

    if composite >= 1.0 or divergence >= 0.75:
        return {
            "risk_state": "CAUTION",
            "recommended_action": "REDUCE_SIZE",
            "can_execute_now": True,
            "max_position_multiplier": 0.35,
            "operator_guidance": "Reduce size and avoid aggressive routing. SPY microstructure is unstable.",
        }

    if composite >= 0.85 or divergence >= 0.50:
        return {
            "risk_state": "EARLY_CAUTION",
            "recommended_action": "SELECTIVE_EXECUTE",
            "can_execute_now": True,
            "max_position_multiplier": 0.75,
            "operator_guidance": "Execute selectively. Prefer lower urgency execution and monitor spread/depth behavior.",
        }

    return {
        "risk_state": "NORMAL",
        "recommended_action": "EXECUTE_FULL",
        "can_execute_now": True,
        "max_position_multiplier": 1.0,
        "operator_guidance": "SPY microstructure appears stable. Normal execution is acceptable.",
    }


def main() -> None:
    rows = load_rows()
    if not rows:
        raise FileNotFoundError("Run `python3 equities/spy_probe.py` first.")

    latest = rows[-1]

    spread_dij = safe_float(latest.get("spread_dij"))
    depth_dij = safe_float(latest.get("depth_dij"))
    qtu_dij = safe_float(latest.get("quote_trade_ratio_dij"))
    composite = safe_float(latest.get("composite_dij"))
    divergence = safe_float(latest.get("divergence"))

    action = classify_action(composite, spread_dij, depth_dij, qtu_dij, divergence)

    payload = {
        "schema_version": "supt.spy_execution_guidance.v1",
        "production_connected": False,
        "experimental": True,
        "symbol": latest.get("symbol", "SPY"),
        "timestamp": latest.get("timestamp"),
        "regime": latest.get("regime"),
        "composite_d_ij": composite,
        "spread_d_ij": spread_dij,
        "depth_d_ij": depth_dij,
        "quote_trade_ratio_d_ij": qtu_dij,
        "divergence": divergence,
        **action,
        "note": "Experimental equities substrate layer only. Not connected to Ethereum production decision API.",
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
