from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from equities.spy_outcome_schema import (
    SCHEMA_FROZEN_AT,
    SCHEMA_HASH,
    SCHEMA_VERSION,
    is_bad_window,
)


@dataclass
class OutcomeReceipt:
    window_id: str
    bar_open_utc: str
    bar_duration_s: float
    d_ij_channel_1: float
    d_ij_channel_2: float
    d_ij_channel_3: float
    composite_d_ij: float
    regime_band: str
    decision_state: str
    horizon_seconds: float
    horizon_end_utc: str
    adverse_mid_move_bps_horizon_30s: Optional[float] = None
    spread_expansion_ratio_horizon_30s: Optional[float] = None
    depth_collapse_ratio_horizon_30s: Optional[float] = None
    quote_to_trade_ratio_horizon_30s: Optional[float] = None
    realized_spread_bps_horizon_30s: Optional[float] = None
    effective_cost_vs_mid_bps_horizon_30s: Optional[float] = None
    is_bad: bool = False
    triggered_rules: str = ""
    n_rules_triggered: int = 0
    schema_version: str = SCHEMA_VERSION
    schema_frozen_at: str = SCHEMA_FROZEN_AT
    schema_hash: str = SCHEMA_HASH
    receipt_written_at: str = ""
    provider: str = ""
    provider_data_hash: str = ""


class SPYOutcomeTracker:
    CSV_FIELDS = list(OutcomeReceipt.__dataclass_fields__.keys())

    def __init__(self, receipts_path: str, expected_schema_hash: str):
        self.receipts_path = receipts_path

        if expected_schema_hash != SCHEMA_HASH:
            raise RuntimeError(
                f"Schema hash mismatch. Expected {expected_schema_hash}, got {SCHEMA_HASH}"
            )

        if not os.path.exists(receipts_path):
            os.makedirs(os.path.dirname(receipts_path), exist_ok=True)

            with open(receipts_path, "w", newline="", encoding="utf-8") as f:
                f.write("# SUPT SPY Outcome Receipts\n")
                f.write(f"# Schema version:  {SCHEMA_VERSION}\n")
                f.write(f"# Schema frozen:   {SCHEMA_FROZEN_AT}\n")
                f.write(f"# Schema hash:     {SCHEMA_HASH}\n")
                f.write(f"# File created:    {datetime.now(timezone.utc).isoformat()}\n")
                f.write("# Notice:          This file is APPEND-ONLY. Edits invalidate receipts.\n")

                writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
                writer.writeheader()

    def append(self, receipt: OutcomeReceipt) -> None:
        if receipt.schema_hash != SCHEMA_HASH:
            raise RuntimeError("Receipt schema hash mismatch. Receipt rejected.")

        metrics = {
            "adverse_mid_move_bps_horizon_30s": receipt.adverse_mid_move_bps_horizon_30s,
            "spread_expansion_ratio_horizon_30s": receipt.spread_expansion_ratio_horizon_30s,
            "depth_collapse_ratio_horizon_30s": receipt.depth_collapse_ratio_horizon_30s,
            "quote_to_trade_ratio_horizon_30s": receipt.quote_to_trade_ratio_horizon_30s,
            "realized_spread_bps_horizon_30s": receipt.realized_spread_bps_horizon_30s,
            "effective_cost_vs_mid_bps_horizon_30s": receipt.effective_cost_vs_mid_bps_horizon_30s,
        }

        is_bad, triggered = is_bad_window(metrics)
        actual = [x for x in triggered if not x.startswith("MISSING:")]

        receipt.is_bad = is_bad
        receipt.triggered_rules = ",".join(triggered)
        receipt.n_rules_triggered = len(actual)
        receipt.receipt_written_at = datetime.now(timezone.utc).isoformat()

        with open(self.receipts_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS)
            row = asdict(receipt)
            row["is_bad"] = "TRUE" if receipt.is_bad else "FALSE"
            writer.writerow(row)

    def count_receipts(self) -> int:
        if not os.path.exists(self.receipts_path):
            return 0

        n = 0
        with open(self.receipts_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or line.startswith("window_id"):
                    continue
                if line.strip():
                    n += 1
        return n
