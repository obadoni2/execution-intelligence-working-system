from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path


OUT = Path("planetary/data/forecast_receipts.csv")


FIELDS = [
    "forecast_id",
    "created_at",
    "target_window_start",
    "target_window_end",
    "forecast_text",
    "forecast_hash",
    "status",
    "outcome",
    "notes",
]


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def init_file() -> None:
    if OUT.exists():
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()


def append_forecast(
    forecast_id: str,
    target_start: str,
    target_end: str,
    forecast_text: str,
) -> None:
    init_file()

    row = {
        "forecast_id": forecast_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_window_start": target_start,
        "target_window_end": target_end,
        "forecast_text": forecast_text,
        "forecast_hash": hash_text(forecast_text),
        "status": "PENDING",
        "outcome": "",
        "notes": "Read-only planetary forecast receipt. Not connected to production execution decisions.",
    }

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerow(row)

    print("Forecast receipt appended:")
    print(row)


def main() -> None:
    append_forecast(
        forecast_id="PLANETARY_2026_DEC_WINDOW_001",
        target_start="2026-12-21",
        target_end="2027-01-10",
        forecast_text=(
            "Between 2026-12-21 and 2027-01-10, the read-only planetary channel "
            "will be evaluated for whether planetary_b_dij enters or remains near "
            "COHERENCE/CLUTCH behavior. This forecast is observational only and not "
            "connected to production execution decisions."
        ),
    )


if __name__ == "__main__":
    main()
