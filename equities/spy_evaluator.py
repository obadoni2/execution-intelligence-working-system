from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


INPUT_CSV = Path("equities/data/spy_probe_output.csv")
SUMMARY_CSV = Path("equities/data/spy_eval_summary.csv")


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


def evaluate() -> None:
    rows = load_rows()
    if not rows:
        print("No SPY probe output found. Run spy_probe first.")
        return

    total = len(rows)
    clutch = [r for r in rows if r.get("regime") == "CLUTCH"]
    coherence = [r for r in rows if r.get("regime") == "COHERENCE"]

    summary = {
        "instrument": "SPY",
        "total_windows": total,
        "clutch_count": len(clutch),
        "coherence_count": len(coherence),
        "clutch_rate": len(clutch) / total if total else 0.0,
        "avg_composite_dij": sum(safe_float(r.get("composite_dij")) for r in rows) / total,
        "avg_divergence": sum(safe_float(r.get("divergence")) for r in rows) / total,
        "production_connected": False,
        "note": "Experimental equities substrate test only.",
    }

    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(summary)
    print(f"Wrote summary to {SUMMARY_CSV}")


if __name__ == "__main__":
    evaluate()
