from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/execution_outcome_validation.csv")

st.set_page_config(
    page_title="Execution Outcome Validation",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Execution Outcome Validation")
st.caption("Tracks what happened in the market after ALLOW / REDUCE_SIZE / PAUSE / BLOCK decisions.")


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
    st.info("No execution outcome validation rows yet. Run live.execution_outcome_validator first.")
    st.stop()

total = len(rows)
counts = {}

for row in rows:
    k = row.get("execution_outcome", "UNKNOWN")
    counts[k] = counts.get(k, 0) + 1

confirmed = counts.get("PROTECTION_CONFIRMED", 0) + counts.get("ALLOW_CONFIRMED", 0)
adverse = counts.get("ALLOW_ADVERSE", 0)
opportunity_cost = counts.get("OPPORTUNITY_COST", 0)
pending = counts.get("PENDING", 0)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Outcome Rows", total)

with c2:
    st.metric("Confirmed Rate", f"{confirmed / total * 100:.2f}%")

with c3:
    st.metric("Adverse Allows", adverse)

with c4:
    st.metric("Opportunity Cost", opportunity_cost)

c5, c6 = st.columns(2)

with c5:
    st.metric("Pending Outcomes", pending)

with c6:
    avg_protection = sum(fnum(r.get("protection_score")) for r in rows) / total
    st.metric("Avg Protection Score", f"{avg_protection:.3f}")

st.divider()

st.subheader("Outcome Counts")
outcome_rows = [{"outcome": k, "count": v} for k, v in counts.items()]
st.dataframe(outcome_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Outcome Validation Rows")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Outcome")
st.json(rows[-1])
