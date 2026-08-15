from __future__ import annotations

from pathlib import Path

from equities.spy_outcome_schema import SCHEMA_HASH
from equities.spy_outcome_tracker import SPYOutcomeTracker


PROD_PATH = Path("equities/data/spy_outcomes.csv")


def main() -> None:
    if PROD_PATH.exists():
        raise RuntimeError(
            f"{PROD_PATH} already exists. Initialization is one-shot. "
            "Archive the existing file first. Receipts are append-only."
        )

    tracker = SPYOutcomeTracker(
        receipts_path=str(PROD_PATH),
        expected_schema_hash=SCHEMA_HASH,
    )

    print(f"Initialized {PROD_PATH}")
    print(f"Schema hash: {SCHEMA_HASH}")
    print(f"Receipt count: {tracker.count_receipts()}")


if __name__ == "__main__":
    main()
