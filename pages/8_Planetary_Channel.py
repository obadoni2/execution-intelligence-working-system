from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


PROBE = Path("planetary/data/planetary_probe_output.csv")
FORECASTS = Path("planetary/data/forecast_receipts.csv")

st.set_page_config(
    page_title="Planetary Channel",
    page_icon="🪐",
    layout="wide",
)

st.title("🪐 Planetary Channel")
st.caption("Read-only experimental channel. Not connected to production execution decisions.")

st.warning(
    "This layer is observational only. Ethereum and SPY remain the execution-intelligence layers."
)


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


probe_rows = load_csv(PROBE)
forecast_rows = load_csv(FORECASTS)

if not probe_rows:
    st.error("No planetary probe output found. Run planetary_ingest and planetary_probe first.")
    st.stop()

latest = probe_rows[-1]

st.subheader("Latest Planetary Probe Reading")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Latest date", latest.get("date"))

with c2:
    st.metric("Planetary A d_ij", latest.get("planetary_a_dij"))

with c3:
    st.metric("Planetary B d_ij", latest.get("planetary_b_dij"))

with c4:
    st.metric("Decision connected?", latest.get("production_decision_connected"))

c5, c6 = st.columns(2)

with c5:
    st.metric("Planetary A regime", latest.get("planetary_a_regime"))

with c6:
    st.metric("Planetary B regime", latest.get("planetary_b_regime"))

st.divider()

st.subheader("Forecast Receipts")

if forecast_rows:
    st.dataframe(forecast_rows, use_container_width=True, hide_index=True)
else:
    st.info("No forecast receipts found yet.")

st.divider()

st.subheader("Recent Planetary Probe History")
st.dataframe(probe_rows[-100:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Raw Latest Reading")
st.json(latest)
