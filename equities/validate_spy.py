from __future__ import annotations

import csv
from pathlib import Path

INPUT = Path("equities/data/spy_real.csv")
OUTPUT = Path("equities/data/validation/spy_validation_receipt.csv")


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(
            "Missing equities/data/spy_real.csv. "
            "Add real SPY market data before validation."
        )

    with INPUT.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if len(rows) < 1000:
        raise ValueError(
            f"Need at least 1,000 rows for validation. Found {len(rows)}."
        )

    print(f"SPY validation input accepted: {len(rows)} rows")
    print("Next: run spy_probe.py, spy_evaluator.py, then outcome scoring.")


if __name__ == "__main__":
    main()
