from __future__ import annotations

import csv
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


SNAPSHOTS = Path("live/data/gateio_market_snapshots.csv")
RECEIPTS = Path("live/data/live_stress_receipts.csv")
ALERTS = Path("live/data/live_alerts.csv")

SLEEP_SECONDS = 10


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for row in rows:
        out[row["symbol"]] = row
    return out


def write_alert(alert: Dict[str, Any]) -> None:
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    exists = ALERTS.exists()

    with ALERTS.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(alert.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(alert)


def detect_precursors() -> None:
    receipts = load_csv(RECEIPTS)
    if len(receipts) < 2:
        return

    by_symbol = {}
    for row in receipts:
        by_symbol.setdefault(row["symbol"], []).append(row)

    now = datetime.now(timezone.utc).isoformat()

    for symbol, rows in by_symbol.items():
        if len(rows) < 2:
            continue

        prev = rows[-2]
        curr = rows[-1]

        spread_delta = fnum(curr.get("spread_bps")) - fnum(prev.get("spread_bps"))
        score_delta = fnum(curr.get("stress_score")) - fnum(prev.get("stress_score"))
        imbalance_delta = fnum(curr.get("trade_imbalance")) - fnum(prev.get("trade_imbalance"))

        alerts = []

        if spread_delta > 2.0:
            alerts.append("SPREAD_EXPANDING_FAST")

        if score_delta > 0.15:
            alerts.append("STRESS_SCORE_JUMP")

        if imbalance_delta > 0.20:
            alerts.append("IMBALANCE_SPIKE")

        if curr.get("regime") != prev.get("regime"):
            alerts.append(f"REGIME_TRANSITION_{prev.get('regime')}_TO_{curr.get('regime')}")

        if alerts:
            confidence = min(
                1.0,
                0.35
                + max(spread_delta, 0) / 10
                + max(score_delta, 0)
                + max(imbalance_delta, 0) / 2,
            )

            alert = {
                "alert_written_at": now,
                "symbol": symbol,
                "alerts": ",".join(alerts),
                "previous_regime": prev.get("regime"),
                "current_regime": curr.get("regime"),
                "previous_guidance": prev.get("guidance"),
                "current_guidance": curr.get("guidance"),
                "spread_delta": round(spread_delta, 6),
                "stress_score_delta": round(score_delta, 6),
                "imbalance_delta": round(imbalance_delta, 6),
                "confidence": round(confidence, 6),
                "provider_hash": curr.get("provider_data_hash"),
            }

            write_alert(alert)
            print(f"ALERT {symbol}: {alert['alerts']} confidence={alert['confidence']}")


def run_once() -> None:
    subprocess.run(
        ["python", "-m", "live.gateio_market_adapter"],
        check=True,
    )

    subprocess.run(
        ["python", "-m", "live.live_regime_engine"],
        check=True,
    )

    detect_precursors()


def main() -> None:
    print("Starting live intelligence loop...")
    print(f"Interval: {SLEEP_SECONDS}s")
    print("CTRL+C to stop")

    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"Loop error: {exc}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
