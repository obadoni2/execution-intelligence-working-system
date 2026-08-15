from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
import streamlit as st


st.set_page_config(
    page_title="SUPT Execution Guidance",
    page_icon="🧭",
    layout="wide",
)

API_URL = os.getenv(
    "SUPT_API_URL",
    "http://eth-monitor-api:8000",
)


def fetch_json(path: str) -> dict:
    url = f"{API_URL}{path}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


st.title("🧭 SUPT Execution Guidance")
st.caption(
    "Buyer-facing execution guidance powered by the live SUPT decision API."
)

st.info(
    "This page consumes `/v1/execution-guidance` from the API. "
    "The dashboard is not recomputing the decision."
)

refresh = st.button("Refresh guidance", type="primary")

try:
    guidance = fetch_json("/v1/execution-guidance")

    recommended_action = guidance.get("recommended_action", "UNKNOWN")
    risk_state = guidance.get("risk_state", "UNKNOWN")
    can_execute = guidance.get("can_execute_now")
    viability = guidance.get("viability_score")
    bad_rate = guidance.get("expected_bad_rate")
    max_multiplier = guidance.get("max_position_multiplier")
    operator_guidance = guidance.get("operator_guidance", "")
    reason = guidance.get("reason", "")
    confidence = guidance.get("confidence", "unknown")

    st.subheader("Current Operator Guidance")

    if recommended_action == "PAUSE":
        st.error(f"Recommended Action: {recommended_action}")
    elif recommended_action == "REDUCE_SIZE":
        st.warning(f"Recommended Action: {recommended_action}")
    elif recommended_action == "SELECTIVE_EXECUTE":
        st.warning(f"Recommended Action: {recommended_action}")
    elif recommended_action == "RESUME_GRADUALLY":
        st.info(f"Recommended Action: {recommended_action}")
    elif recommended_action == "EXECUTE_FULL":
        st.success(f"Recommended Action: {recommended_action}")
    else:
        st.write(f"Recommended Action: {recommended_action}")

    st.markdown(f"### {operator_guidance}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Can execute now?", str(can_execute))

    with col2:
        st.metric("Risk state", risk_state)

    with col3:
        if viability is not None:
            st.metric("Viability score", f"{float(viability) * 100:.2f}%")
        else:
            st.metric("Viability score", "N/A")

    with col4:
        if bad_rate is not None:
            st.metric("Expected bad rate", f"{float(bad_rate) * 100:.2f}%")
        else:
            st.metric("Expected bad rate", "N/A")

    col5, col6 = st.columns(2)

    with col5:
        if max_multiplier is not None:
            st.metric("Max position multiplier", f"{float(max_multiplier):.2f}x")
        else:
            st.metric("Max position multiplier", "N/A")

    with col6:
        st.metric("Confidence", str(confidence))

    st.divider()

    st.subheader("Reason")
    st.write(reason)

    st.divider()

    st.subheader("Raw API Response")
    st.json(guidance)

    st.caption(
        f"Last dashboard refresh: {datetime.now(timezone.utc).isoformat()}"
    )

except Exception as exc:
    st.error("Failed to fetch execution guidance from API.")
    st.code(str(exc))
    st.warning(
        "Make sure the API container is running and reachable at "
        f"`{API_URL}`."
    )
