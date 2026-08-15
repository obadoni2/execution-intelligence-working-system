from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/execution_outcome_feedback_loop.csv")

st.set_page_config(
    page_title="Execution Outcome Feedback",
    page_icon="🔁",
    layout="wide",
)

st.title("🔁 Execution Outcome Feedback Loop")
st.caption("Feeds realistic execution quality back into policy learning and trust evaluation.")


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
    st.info("No execution feedback rows yet. Run live.execution_outcome_feedback_loop first.")
    st.stop()

latest = {}
for row in rows:
    latest[row.get("symbol")] = row

latest_rows = list(latest.values())

confirmed = sum(1 for r in latest_rows if r.get("feedback_label") == "EXECUTION_CONFIRMED")
acceptable = sum(1 for r in latest_rows if r.get("feedback_label") == "EXECUTION_ACCEPTABLE")
weak = sum(1 for r in latest_rows if r.get("feedback_label") == "EXECUTION_WEAK")
degraded = sum(1 for r in latest_rows if r.get("feedback_label") == "EXECUTION_DEGRADED")
no_feedback = sum(1 for r in latest_rows if r.get("feedback_label") == "NO_EXECUTION_FEEDBACK")

avg_score = sum(fnum(r.get("net_execution_score")) for r in latest_rows) / len(latest_rows)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Confirmed", confirmed)

with c2:
    st.metric("Acceptable", acceptable)

with c3:
    st.metric("Weak / Degraded", weak + degraded)

with c4:
    st.metric("No Feedback", no_feedback)

c5, c6 = st.columns(2)

with c5:
    st.metric("Avg Net Exec Score", f"{avg_score:.3f}")

with c6:
    st.metric("Symbols", len(latest_rows))

st.divider()

st.subheader("Latest Execution Feedback")
st.dataframe(latest_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Recent Feedback Receipts")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Feedback Row")
st.json(rows[-1])
