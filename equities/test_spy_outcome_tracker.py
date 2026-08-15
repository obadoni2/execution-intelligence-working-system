from __future__ import annotations

from equities.spy_outcome_schema import SCHEMA_HASH
from equities.spy_outcome_tracker import OutcomeReceipt, SPYOutcomeTracker


RECEIPTS_PATH = "equities/data/spy_outcomes.csv"


def main() -> None:
    tracker = SPYOutcomeTracker(
        receipts_path=RECEIPTS_PATH,
        expected_schema_hash=SCHEMA_HASH,
    )

    clean = OutcomeReceipt(
        window_id="SMOKE_CLEAN_001",
        bar_open_utc="2026-05-13T12:50:00Z",
        bar_duration_s=1.0,
        d_ij_channel_1=0.42,
        d_ij_channel_2=0.51,
        d_ij_channel_3=0.39,
        composite_d_ij=0.51,
        regime_band="COHERENCE",
        decision_state="NORMAL",
        horizon_seconds=30.0,
        horizon_end_utc="2026-05-13T12:50:30Z",
        adverse_mid_move_bps_horizon_30s=0.3,
        spread_expansion_ratio_horizon_30s=1.1,
        depth_collapse_ratio_horizon_30s=0.85,
        quote_to_trade_ratio_horizon_30s=12.0,
        realized_spread_bps_horizon_30s=0.2,
        effective_cost_vs_mid_bps_horizon_30s=0.4,
        provider="smoke_test",
        provider_data_hash="0" * 64,
    )

    bad = OutcomeReceipt(
        window_id="SMOKE_BAD_001",
        bar_open_utc="2026-05-13T12:55:00Z",
        bar_duration_s=1.0,
        d_ij_channel_1=1.85,
        d_ij_channel_2=2.40,
        d_ij_channel_3=1.92,
        composite_d_ij=2.40,
        regime_band="SUB_FLOOR",
        decision_state="HIGH_STRESS",
        horizon_seconds=30.0,
        horizon_end_utc="2026-05-13T12:55:30Z",
        adverse_mid_move_bps_horizon_30s=4.7,
        spread_expansion_ratio_horizon_30s=4.2,
        depth_collapse_ratio_horizon_30s=0.18,
        quote_to_trade_ratio_horizon_30s=22.0,
        realized_spread_bps_horizon_30s=2.1,
        effective_cost_vs_mid_bps_horizon_30s=3.6,
        provider="smoke_test",
        provider_data_hash="f" * 64,
    )

    tracker.append(clean)
    tracker.append(bad)

    print(f"Receipt count: {tracker.count_receipts()}")
    print("Smoke test appended 2 receipts successfully.")


if __name__ == "__main__":
    main()
