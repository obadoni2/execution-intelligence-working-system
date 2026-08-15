from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/execution_orchestrator_receipts.csv")

st.set_page_config(
    page_title="Execution Orchestrator",
    page_icon="🎛️",
    layout="wide",
)

st.title("🎛️ Execution Orchestrator")
st.caption("Coordinates policy stage, trust, risk gate, and execution route. Safe mode only.")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


rows = load_rows(DATA)

if not rows:
    st.info("No orchestrator receipts yet. Run live.execution_orchestrator first.")
    st.stop()

latest = {}
for row in rows:
    latest[row.get("symbol")] = row

latest_rows = list(latest.values())

actions = {}
for row in latest_rows:
    action = row.get("orchestrator_action", "UNKNOWN")
    actions[action] = actions.get(action, 0) + 1

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Symbols", len(latest_rows))

with c2:
    st.metric("Paper Trades", actions.get("PAPER_TRADE", 0))

with c3:
    st.metric("Blocked", actions.get("BLOCKED", 0))

with c4:
    st.metric("No Action", actions.get("NO_ACTION", 0))

st.divider()

st.subheader("Latest Orchestrator Decisions")
st.dataframe(latest_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Recent Receipts")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Receipt")
st.json(rows[-1])
