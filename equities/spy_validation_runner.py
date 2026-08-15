from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any, Dict, List

from equities.spy_horizon_labeler import label_rows
from equities.spy_outcome_schema import SCHEMA_HASH
from equities.spy_outcome_tracker import OutcomeReceipt, SPYOutcomeTracker
from equities.spy_provider_adapter import normalize_provider_rows
from equities.spy_probe import run_probe


NORMALIZED_PATH = Path("equities/data/provider/spy_provider_normalized.csv")
SPY_SAMPLE_PATH = Path("equities/data/spy_sample.csv")
PROBE_OUTPUT_PATH = Path("equities/data/spy_probe_output.csv")
LABELS_PATH = Path("equities/data/validation/spy_horizon_labels.csv")
RECEIPTS_PATH = Path("equities/data/spy_outcomes.csv")


def load_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def regime_to_state(regime: str, composite: float) -> str:
    if composite >= 2.0:
        return "HIGH_STRESS"
    if composite >= 1.25:
        return "CAUTION"
    if composite >= 1.0:
        return "EARLY_CAUTION"
    if regime == "COHERENCE":
        return "NORMAL"
    return "NORMAL"


def main() -> None:
    print("Step 1: Normalize provider data")
    provider_rows = normalize_provider_rows()

    print("Step 2: Copy normalized provider data into SPY probe input")
    shutil.copyfile(NORMALIZED_PATH, SPY_SAMPLE_PATH)

    print("Step 3: Run frozen SPY probe")
    run_probe()

    print("Step 4: Compute 30-second horizon labels")
    label_rows()

    print("Step 5: Append schema-bound receipts")
    probe_rows = load_csv(PROBE_OUTPUT_PATH)
    label_rows_loaded = load_csv(LABELS_PATH)

    labels_by_ts = {r["timestamp"]: r for r in label_rows_loaded}

    tracker = SPYOutcomeTracker(
        receipts_path=str(RECEIPTS_PATH),
        expected_schema_hash=SCHEMA_HASH,
    )

    appended = 0

    for row in probe_rows:
        ts = row["timestamp"]

        if ts not in labels_by_ts:
            continue

        label = labels_by_ts[ts]
        composite = float(row["composite_dij"])

        receipt = OutcomeReceipt(
            window_id=f"SPY_{ts}",
            bar_open_utc=ts,
            bar_duration_s=1.0,
            d_ij_channel_1=float(row["spread_dij"]),
            d_ij_channel_2=float(row["quote_trade_ratio_dij"]),
            d_ij_channel_3=float(row["depth_dij"]),
            composite_d_ij=composite,
            regime_band=row["regime"],
            decision_state=regime_to_state(row["regime"], composite),
            horizon_seconds=30.0,
            horizon_end_utc=label["horizon_end_utc"],
            adverse_mid_move_bps_horizon_30s=float(label["adverse_mid_move_bps_horizon_30s"]),
            spread_expansion_ratio_horizon_30s=float(label["spread_expansion_ratio_horizon_30s"]),
            depth_collapse_ratio_horizon_30s=float(label["depth_collapse_ratio_horizon_30s"]),
            quote_to_trade_ratio_horizon_30s=float(label["quote_to_trade_ratio_horizon_30s"]),
            realized_spread_bps_horizon_30s=float(label["realized_spread_bps_horizon_30s"]),
            effective_cost_vs_mid_bps_horizon_30s=float(label["effective_cost_vs_mid_bps_horizon_30s"]),
            provider=label.get("provider", "local_csv"),
            provider_data_hash=label.get("provider_data_hash", ""),
        )

        tracker.append(receipt)
        appended += 1

    print(f"Appended {appended} SPY validation receipts to {RECEIPTS_PATH}")
    print(f"Total receipt count: {tracker.count_receipts()}")


if __name__ == "__main__":
    main()
