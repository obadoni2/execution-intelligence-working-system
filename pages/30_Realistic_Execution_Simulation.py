from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/realistic_execution_simulation.csv")

st.set_page_config(
    page_title="Realistic Execution Simulation",
    page_icon="⏱️",
    layout="wide",
)

st.title("⏱️ Realistic Execution Simulation")
st.caption("Models latency, slippage, partial fills, liquidity constraints, fees, and execution failure.")


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
    st.info("No realistic execution rows yet. Run live.realistic_execution_simulator first.")
    st.stop()

latest = {}
for row in rows:
    latest[row.get("symbol")] = row

latest_rows = list(latest.values())

filled = sum(1 for r in latest_rows if r.get("execution_status") == "FILLED_REALISTIC_EXECUTION")
partial = sum(1 for r in latest_rows if r.get("execution_status") == "PARTIAL_REALISTIC_EXECUTION")
failed = sum(1 for r in latest_rows if r.get("execution_status") == "FAILED_REALISTIC_EXECUTION")
skipped = sum(1 for r in latest_rows if r.get("execution_status") == "SKIPPED")

avg_latency = sum(fnum(r.get("latency_ms")) for r in latest_rows) / len(latest_rows)
total_cost = sum(fnum(r.get("total_execution_cost")) for r in latest_rows)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Filled", filled)

with c2:
    st.metric("Partial", partial)

with c3:
    st.metric("Failed", failed)

with c4:
    st.metric("Skipped", skipped)

c5, c6 = st.columns(2)

with c5:
    st.metric("Avg Latency", f"{avg_latency:.0f} ms")

with c6:
    st.metric("Total Exec Cost", f"{total_cost:.4f}")

st.divider()

st.subheader("Latest Realistic Execution Rows")
st.dataframe(latest_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Recent Realistic Execution Receipts")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Receipt")
st.json(rows[-1])
