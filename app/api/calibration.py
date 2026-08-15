from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


CALIBRATION_VERSION = "v1.0.0-n506"


CALIBRATION: Dict[str, Any] = {
    "schema_version": "supt.calibration.v1",
    "version": CALIBRATION_VERSION,
    "validation_window": {
        "block_start": 19000149,
        "block_end": 25015827,
        "n_windows": 506,
        "approx_hours_mainnet": 20052.26,
    },
    "state_calibration": {
        "NORMAL": {
            "ordinal": 0,
            "n": 117,
            "future_bad_rate": 0.0085,
            "viability_score": 0.9915,
            "execution_mode": "EXECUTE_FULL",
        },
        "EARLY_CAUTION": {
            "ordinal": 1,
            "n": 23,
            "future_bad_rate": 0.0435,
            "viability_score": 0.9565,
            "execution_mode": "SELECTIVE_EXECUTE",
        },
        "RECOVERY": {
            "ordinal": 2,
            "n": 152,
            "future_bad_rate": 0.0592,
            "viability_score": 0.9408,
            "execution_mode": "RESUME_GRADUALLY",
        },
        "CAUTION": {
            "ordinal": 3,
            "n": 172,
            "future_bad_rate": 0.2791,
            "viability_score": 0.7209,
            "execution_mode": "REDUCE_SIZE",
        },
        "HIGH_STRESS": {
            "ordinal": 4,
            "n": 42,
            "future_bad_rate": 1.0,
            "viability_score": 0.0,
            "execution_mode": "PAUSE",
        },
    },
    "transition_calibration": {
        "n_events": 8,
        "median_gas_channel_lead_blocks": 18.0,
        "mean_gas_channel_lead_blocks": 15.86,
        "pre_divergence_rate": 0.875,
        "pre_agent_shift_rate": 0.875,
    },
    "discrimination": {
        "pause_precision": 1.0,
        "pause_rate": 0.083,
        "bad_rate_when_paused": 1.0,
        "bad_rate_when_executed": 0.1272,
        "discrimination_gap": 0.8728,
        "verdict": "strong_discrimination",
    },
    "probe": {
        "alpha": 0.01,
        "tail_n": 50,
        "rolling_window_blocks": 150,
    },
}


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def calibration_sha() -> str:
    payload = dict(CALIBRATION)
    payload.pop("receipt_sha", None)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def get_calibration() -> Dict[str, Any]:
    payload = dict(CALIBRATION)
    payload["receipt_sha"] = calibration_sha()
    return payload


def get_state_calibration(state: str) -> Dict[str, Any]:
    state = state.upper()
    return CALIBRATION["state_calibration"].get(
        state,
        CALIBRATION["state_calibration"]["NORMAL"],
    )
