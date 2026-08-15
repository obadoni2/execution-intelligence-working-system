from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path


OUT = Path("planetary/data/planetary_series.csv")


def pseudo_angle(day_index: int, period: float, phase: float = 0.0) -> float:
    return (360.0 * ((day_index / period) + phase)) % 360.0


def sep(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def main() -> None:
    start = date(2026, 1, 1)
    end = date(2027, 1, 15)

    rows = []
    d = start

    while d <= end:
        i = (d - start).days

        sun = pseudo_angle(i, 365.25, 0.00)
        mercury = pseudo_angle(i, 87.97, 0.15)
        venus = pseudo_angle(i, 224.70, 0.35)
        mars = pseudo_angle(i, 686.98, 0.55)

        mer_ven = sep(mercury, venus)
        mer_mars = sep(mercury, mars)
        ven_mars = sep(venus, mars)

        sun_ven = sep(sun, venus)
        sun_mars = sep(sun, mars)

        planetary_b = max(mer_ven, mer_mars, ven_mars)
        planetary_a = max(sun_ven, sun_mars, ven_mars)

        rows.append(
            {
                "date": d.isoformat(),
                "sun": round(sun, 6),
                "mercury": round(mercury, 6),
                "venus": round(venus, 6),
                "mars": round(mars, 6),
                "planetary_a": round(planetary_a, 6),
                "planetary_b": round(planetary_b, 6),
            }
        )

        d += timedelta(days=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} planetary rows to {OUT}")


if __name__ == "__main__":
    main()
