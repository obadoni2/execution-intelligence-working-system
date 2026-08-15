from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/paper_trading_receipts.csv")

st.set_page_config(
    page_title="Paper Trading Engine",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 Paper Trading Engine")
st.caption("Safe simulation layer. No real orders. No real capital.")


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
    st.info("No paper trading receipts yet. Run live.paper_trading_engine first.")
    st.stop()

latest = {}
for row in rows:
    latest[row.get("symbol")] = row

latest_rows = list(latest.values())

simulated = sum(1 for r in latest_rows if r.get("status") == "OPEN_SIMULATED")
skipped = sum(1 for r in latest_rows if r.get("status") == "SKIPPED")
failed = sum(1 for r in latest_rows if r.get("status") == "FAILED")
total_notional = sum(fnum(r.get("notional")) for r in latest_rows)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Symbols", len(latest_rows))

with c2:
    st.metric("Simulated Trades", simulated)

with c3:
    st.metric("Skipped", skipped)

with c4:
    st.metric("Total Notional", f"{total_notional:.2f}")

c5, c6 = st.columns(2)

with c5:
    st.metric("Failed", failed)

with c6:
    st.metric("Mode", "SAFE PAPER ONLY")

st.divider()

st.subheader("Latest Paper Trading Decisions")
st.dataframe(latest_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Recent Receipts")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Receipt")
st.json(rows[-1])
