from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd


def _hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def export_public_log_from_env() -> None:
    input_path = Path(os.getenv("PUBLIC_LOG_INPUT_PATH", "data/counterfactual_log.csv"))
    output_path = Path(os.getenv("PUBLIC_LOG_OUTPUT_PATH", "data/public_regime_log.jsonl"))

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found.")

    df = pd.read_csv(input_path)

    if df.empty:
        raise RuntimeError("Counterfactual log is empty.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    previous_hash = "GENESIS"

    with output_path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            payload = {
                "timestamp": row.get("timestamp"),
                "chain": row.get("chain"),
                "latest_block": row.get("latest_block"),
                "block_hash": row.get("block_hash"),
                "regime": row.get("regime"),
                "composite_dij": row.get("composite_dij"),
                "tx_dij": row.get("tx_dij"),
                "gas_dij": row.get("gas_dij"),
                "base_fee_dij": row.get("base_fee_dij"),
                "agent_risk_state": row.get("agent_risk_state"),
                "agent_execution_mode": row.get("agent_execution_mode"),
                "previous_hash": previous_hash,
            }

            current_hash = _hash_payload(payload)
            payload["record_hash"] = current_hash

            f.write(json.dumps(payload, default=str) + "\n")

            previous_hash = current_hash

    print("=" * 80)
    print("Public tamper-evident log exported")
    print("=" * 80)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Final hash: {previous_hash}")
    print("=" * 80)
