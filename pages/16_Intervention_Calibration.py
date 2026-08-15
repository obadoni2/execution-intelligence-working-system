from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/intervention_calibration.csv")

st.set_page_config(
    page_title="Intervention Calibration",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Intervention Calibration")
st.caption("Measures whether ALLOW / REDUCE_SIZE / PAUSE / BLOCK decisions were useful or over-defensive.")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


rows = load_rows(DATA)

if not rows:
    st.info("No intervention calibration rows yet. Run live.intervention_calibrator first.")
    st.stop()

total = len(rows)
avg_quality = sum(fnum(r.get("intervention_quality_score")) for r in rows) / total

outcomes = {}
for row in rows:
    k = row.get("intervention_outcome", "UNKNOWN")
    outcomes[k] = outcomes.get(k, 0) + 1

correct = sum(v for k, v in outcomes.items() if k.startswith("CORRECT"))
over = sum(v for k, v in outcomes.items() if "OVERREACTION" in k)
missed = outcomes.get("MISSED_STRESS", 0)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Calibrated Events", total)

with c2:
    st.metric("Avg Quality", f"{avg_quality:.3f}")

with c3:
    st.metric("Correct Rate", f"{correct / total * 100:.2f}%")

with c4:
    st.metric("Overreaction Rate", f"{over / total * 100:.2f}%")

c5, c6 = st.columns(2)

with c5:
    st.metric("Missed Stress Rate", f"{missed / total * 100:.2f}%")

with c6:
    st.metric("Outcome Types", len(outcomes))

st.divider()

st.subheader("Outcome Counts")
outcome_rows = [{"outcome": k, "count": v} for k, v in outcomes.items()]
st.dataframe(outcome_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Calibration Rows")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Calibration Result")
st.json(rows[-1])
