from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("SUPT_API_URL", "http://eth-monitor-api:8000")

st.set_page_config(
    page_title="SPY Lead-Lag Analysis",
    page_icon="⏱️",
    layout="wide",
)

st.title("⏱️ SPY Lead-Lag Analysis")
st.caption("Detects whether individual SPY channels cross stress threshold before composite stress forms.")


def fetch_json(path: str) -> dict:
    url = f"{API_URL}{path}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


try:
    payload = fetch_json("/v1/spy-lead-lag")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Total Rows", payload.get("total_rows"))

    with c2:
        st.metric("Composite Crossings", payload.get("composite_crossing_count"))

    with c3:
        st.metric("Threshold", payload.get("threshold"))

    st.divider()

    st.subheader("Lead Summary by Channel")

    summary = payload.get("lead_summary", {})
    summary_rows = []

    for channel, data in summary.items():
        summary_rows.append(
            {
                "channel": channel,
                "lead_event_count": data.get("lead_event_count"),
                "median_lead_rows": data.get("median_lead_rows"),
                "mean_lead_rows": data.get("mean_lead_rows"),
                "max_lead_rows": data.get("max_lead_rows"),
            }
        )

    st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Leading Channel Counts")
    counts = payload.get("leading_channel_counts", {})
    count_rows = [{"channel": k, "count": v} for k, v in counts.items()]
    st.dataframe(count_rows, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Strongest Current Precursor Signal")

    quote = summary.get("quote_trade_ratio", {})
    max_quote_lead = quote.get("max_lead_rows")

    if max_quote_lead is not None:
        st.warning(
            f"Quote/trade ratio produced the largest observed lead: {max_quote_lead} rows before composite crossing."
        )

    st.divider()

    st.subheader("Recent Transition Events")

    events = payload.get("events", [])
    event_rows = []

    for e in events:
        event_rows.append(
            {
                "timestamp": e.get("timestamp"),
                "composite_cross_index": e.get("composite_cross_index"),
                "composite_dij": e.get("composite_dij"),
                "leading_channel": e.get("leading_channel"),
                "max_lead_rows": e.get("max_lead_rows"),
            }
        )

    st.dataframe(event_rows, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Raw JSON")
    st.json(payload)

except Exception as exc:
    st.error("Failed to fetch SPY lead-lag analysis.")
    st.code(str(exc))
