from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/position_sizing_receipts.csv")

st.set_page_config(
    page_title="Position Sizing Engine",
    page_icon="📐",
    layout="wide",
)

st.title("📐 Position Sizing Engine")
st.caption(
    "Determines how much capital may be allocated based on "
    "trust, confidence, risk, liquidity, spread, and stress."
)


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def fnum(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


rows = load_rows(DATA)

if not rows:
    st.info(
        "No position-sizing receipts yet. "
        "Run live.position_sizing_engine first."
    )
    st.stop()

latest = {}

for row in rows:
    symbol = row.get("symbol")
    if symbol:
        latest[symbol] = row

latest_rows = list(latest.values())

allocated = sum(
    1
    for row in latest_rows
    if row.get("sizing_status") == "ALLOCATED"
)

no_allocation = sum(
    1
    for row in latest_rows
    if row.get("sizing_status") == "NO_ALLOCATION"
)

total_allocated = sum(
    fnum(row.get("capital_allocated"))
    for row in latest_rows
)

average_position_pct = (
    sum(
        fnum(row.get("final_position_pct"))
        for row in latest_rows
    )
    / len(latest_rows)
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Symbols", len(latest_rows))

with c2:
    st.metric("Allocated", allocated)

with c3:
    st.metric("No Allocation", no_allocation)

with c4:
    st.metric(
        "Capital Allocated",
        f"${total_allocated:,.2f}",
    )

c5, c6, c7 = st.columns(3)

with c5:
    st.metric(
        "Average Position",
        f"{average_position_pct:.4f}%",
    )

with c6:
    st.metric(
        "Portfolio Capital",
        f"${fnum(latest_rows[-1].get('portfolio_capital')):,.2f}",
    )

with c7:
    st.metric(
        "Trust",
        latest_rows[-1].get("policy_trust_label"),
    )

st.divider()

st.subheader("Latest Position Sizing Decisions")

table = []

for row in latest_rows:
    table.append({
        "symbol": row.get("symbol"),
        "risk_decision": row.get("risk_decision"),
        "orchestrator_action": row.get(
            "orchestrator_action"
        ),
        "trust": row.get("policy_trust_label"),
        "confidence": row.get(
            "evidence_confidence_label"
        ),
        "stress": fnum(row.get("stress_score")),
        "spread_bps": fnum(row.get("spread_bps")),
        "top_depth": fnum(row.get("top_depth")),
        "position_pct": fnum(
            row.get("final_position_pct")
        ),
        "capital_allocated": fnum(
            row.get("capital_allocated")
        ),
        "status": row.get("sizing_status"),
        "reason": row.get("sizing_reason"),
    })

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Latest Sizing Receipt")
st.json(latest_rows[-1])

st.divider()

st.subheader("Recent Position Sizing History")
st.dataframe(
    rows[-300:],
    use_container_width=True,
    hide_index=True,
)
