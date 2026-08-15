from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/execution_intelligence_receipts.csv")

st.set_page_config(
    page_title="Execution Intelligence",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Execution Intelligence")
st.caption("Decides how orders should be worked: passive, aggressive, sliced, delayed, or avoided.")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


rows = load_rows(DATA)

if not rows:
    st.info("No execution intelligence rows yet. Run live.execution_intelligence first.")
    st.stop()

latest = {}
for row in rows:
    latest[row.get("symbol")] = row

latest_rows = list(latest.values())

styles = {}
for r in latest_rows:
    style = r.get("execution_style", "UNKNOWN")
    styles[style] = styles.get(style, 0) + 1

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Symbols", len(latest_rows))

with c2:
    st.metric("No Execution", styles.get("NO_EXECUTION", 0))

with c3:
    st.metric("Passive/Sliced", styles.get("PASSIVE_LIMIT", 0) + styles.get("SLICED_LIMIT", 0))

with c4:
    st.metric("Aggressive", styles.get("AGGRESSIVE_MARKET", 0))

st.divider()

st.subheader("Execution Style Counts")
st.dataframe(
    [{"execution_style": k, "count": v} for k, v in styles.items()],
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Latest Execution Intelligence Decisions")
st.dataframe(latest_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Receipt")
st.json(rows[-1])
