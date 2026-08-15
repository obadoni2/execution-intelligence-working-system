from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("SUPT_API_URL", "http://eth-monitor-api:8000")

st.set_page_config(
    page_title="SPY Validation Summary",
    page_icon="📊",
    layout="wide",
)

st.title("📊 SPY Validation Summary")
st.caption("Summary metrics from the append-only SPY outcome receipt ledger.")


def fetch_json(path: str) -> dict:
    url = f"{API_URL}{path}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


try:
    payload = fetch_json("/v1/spy-validation-summary")

    total = payload.get("total_receipts", 0)
    bad = payload.get("bad_receipts", 0)
    clean = payload.get("clean_receipts", 0)
    bad_rate = float(payload.get("bad_rate", 0.0)) * 100

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Total Receipts", total)

    with c2:
        st.metric("Bad Receipts", bad)

    with c3:
        st.metric("Clean Receipts", clean)

    with c4:
        st.metric("Bad Rate", f"{bad_rate:.2f}%")

    st.divider()

    st.subheader("Schema Hashes")
    for h in payload.get("schema_hashes", []):
        st.code(h)

    st.subheader("Providers")
    st.write(payload.get("providers", []))

    st.subheader("Provider Data Hashes")
    for h in payload.get("provider_data_hashes", []):
        st.code(h)

    st.divider()

    st.subheader("Decision-State Breakdown")

    state_summary = payload.get("decision_state_summary", {})
    state_rows = []
    for state, data in state_summary.items():
        state_rows.append(
            {
                "decision_state": state,
                "total": data.get("total"),
                "bad": data.get("bad"),
                "clean": data.get("clean"),
                "bad_rate": round(float(data.get("bad_rate", 0.0)) * 100, 2),
            }
        )

    st.dataframe(state_rows, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Triggered Rule Counts")

    rule_counts = payload.get("triggered_rule_counts", {})
    rule_rows = [
        {"rule": rule, "count": count}
        for rule, count in rule_counts.items()
    ]

    if rule_rows:
        st.dataframe(rule_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No triggered rules found.")

    st.divider()

    st.subheader("Raw Summary JSON")
    st.json(payload)

except Exception as exc:
    st.error("Failed to fetch SPY validation summary.")
    st.code(str(exc))
