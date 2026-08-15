from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
import streamlit as st


st.set_page_config(
    page_title="SUPT Decision History",
    page_icon="🧾",
    layout="wide",
)

API_URL = os.getenv("SUPT_API_URL", "http://eth-monitor-api:8000")


def fetch_json(path: str) -> dict:
    url = f"{API_URL}{path}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


st.title("🧾 SUPT Decision History")
st.caption("Read-only audit trail from `/v1/decision-history`.")

with st.sidebar:
    st.header("History Settings")
    limit = st.slider("Number of decisions", min_value=5, max_value=200, value=25, step=5)
    refresh = st.button("Refresh history", type="primary")

try:
    payload = fetch_json(f"/v1/decision-history?limit={limit}")

    summary = payload.get("summary", {})
    decisions = payload.get("decisions", [])
    calibration = payload.get("calibration", {})

    st.subheader("Audit Summary")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Decisions", payload.get("count", 0))

    with c2:
        st.metric("PAUSE", summary.get("pause_count", 0))

    with c3:
        st.metric("REDUCE_SIZE", summary.get("reduce_size_count", 0))

    with c4:
        st.metric("SELECTIVE", summary.get("selective_execute_count", 0))

    with c5:
        st.metric(
            "Avoided Risk",
            f"{float(summary.get('total_avoided_risk_exposure', 0.0)):.4f}",
        )

    st.caption(f"Calibration version: {calibration.get('version')}")
    st.caption(f"Calibration SHA: {calibration.get('receipt_sha')}")

    st.divider()

    st.subheader("Recent Decisions")

    if not decisions:
        st.warning("No decisions found.")
    else:
        table_rows = []
        for d in reversed(decisions):
            risk = d.get("risk_accounting", {})
            table_rows.append(
                {
                    "timestamp": d.get("timestamp_utc"),
                    "block": d.get("block_number"),
                    "risk_state": d.get("risk_state"),
                    "action": d.get("recommended_action"),
                    "should_execute": d.get("should_execute"),
                    "max_size": d.get("max_position_multiplier"),
                    "confidence": d.get("confidence"),
                    "composite": d.get("composite_d_ij"),
                    "gas": d.get("gas_d_ij"),
                    "base_fee": d.get("base_fee_d_ij"),
                    "avoided_risk": risk.get("avoided_risk_exposure"),
                    "decision_hash": d.get("decision_hash"),
                }
            )

        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("Decision Detail")

        selected_index = st.selectbox(
            "Select decision",
            options=list(range(len(decisions))),
            format_func=lambda i: (
                f"{decisions[i].get('timestamp_utc')} | "
                f"{decisions[i].get('recommended_action')} | "
                f"{decisions[i].get('risk_state')} | "
                f"block {decisions[i].get('block_number')}"
            ),
        )

        selected = decisions[selected_index]

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Action", selected.get("recommended_action"))

        with col2:
            st.metric("Risk State", selected.get("risk_state"))

        with col3:
            st.metric("Confidence", selected.get("confidence"))

        with col4:
            st.metric("Should Execute", str(selected.get("should_execute")))

        st.markdown("### Reason")
        st.write(selected.get("reason"))

        st.markdown("### Suggested Action")
        st.write(selected.get("suggested_action"))

        st.markdown("### Decision Hash")
        st.code(selected.get("decision_hash", ""))

        st.markdown("### Raw Decision JSON")
        st.json(selected)

    st.caption(f"Last dashboard refresh: {datetime.now(timezone.utc).isoformat()}")

except Exception as exc:
    st.error("Failed to fetch decision history from API.")
    st.code(str(exc))
    st.warning(f"Make sure API is reachable at `{API_URL}`.")
