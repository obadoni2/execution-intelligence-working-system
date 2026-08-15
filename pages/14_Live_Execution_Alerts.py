from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


ALERTS = Path("live/data/live_alerts.csv")

st.set_page_config(
    page_title="Live Execution Alerts",
    page_icon="🚨",
    layout="wide",
)

st.title("🚨 Live Execution Alerts")
st.caption("Real-time precursor, regime transition, and execution-risk alerts. No live orders.")


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


rows = load_rows(ALERTS)

if not rows:
    st.info("No live alerts yet. Run the live intelligence loop.")
    st.stop()

latest = rows[-1]

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Total Alerts", len(rows))

with c2:
    st.metric("Latest Symbol", latest.get("symbol"))

with c3:
    st.metric("Latest Confidence", latest.get("confidence"))

with c4:
    st.metric("Current Regime", latest.get("current_regime"))

st.divider()

st.subheader("Latest Alert")
st.json(latest)

st.divider()

st.subheader("Alert History")
table = sorted(rows, key=lambda r: r.get("alert_written_at", ""), reverse=True)
st.dataframe(table[:200], use_container_width=True, hide_index=True)
