from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
import streamlit as st


st.set_page_config(
    page_title="SUPT Decision Outcomes",
    page_icon="✅",
    layout="wide",
)

API_URL = os.getenv("SUPT_API_URL", "http://eth-monitor-api:8000")


def fetch_json(path: str) -> dict:
    url = f"{API_URL}{path}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


st.title("✅ SUPT Decision Outcomes")
st.caption("Read-only accountability layer from `/v1/decision-outcomes`.")

with st.sidebar:
    st.header("Outcome Settings")
    limit = st.slider("Number of outcomes", min_value=10, max_value=200, value=50, step=10)
    st.button("Refresh outcomes", type="primary")

try:
    payload = fetch_json(f"/v1/decision-outcomes?limit={limit}")

    summary = payload.get("summary", {})
    outcomes = payload.get("outcomes", [])
    calibration = payload.get("calibration", {})

    st.subheader("Outcome Summary")

    count = payload.get("count", 0)
    accuracy = float(summary.get("accuracy", 0.0)) * 100
    total_avoided = float(summary.get("total_avoided_risk_exposure", 0.0))

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Outcomes", count)

    with c2:
        st.metric("Correct", summary.get("correct_count", 0))

    with c3:
        st.metric("Accuracy", f"{accuracy:.2f}%")

    with c4:
        st.metric("Future Bad", summary.get("future_bad_count", 0))

    with c5:
        st.metric("Avoided Risk", f"{total_avoided:.4f}")

    st.caption(f"Calibration version: {calibration.get('version')}")
    st.caption(f"Calibration SHA: {calibration.get('receipt_sha')}")

    st.divider()

    st.subheader("Recent Decision Outcomes")

    if not outcomes:
        st.warning("No outcomes found. Run `scripts/evaluate_decision_outcomes.py` first.")
    else:
        table_rows = []
        for row in reversed(outcomes):
            table_rows.append(
                {
                    "timestamp": row.get("timestamp_utc"),
                    "block": row.get("block_number"),
                    "risk_state": row.get("risk_state"),
                    "action": row.get("action"),
                    "future_bad": row.get("future_bad"),
                    "future_bad_count": row.get("future_bad_count"),
                    "correct": row.get("correct"),
                    "confidence": row.get("confidence"),
                    "composite": row.get("composite_d_ij"),
                    "gas": row.get("gas_d_ij"),
                    "base_fee": row.get("base_fee_d_ij"),
                    "avoided_risk": row.get("avoided_risk_exposure"),
                }
            )

        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("Outcome Detail")

        selected_index = st.selectbox(
            "Select outcome",
            options=list(range(len(outcomes))),
            format_func=lambda i: (
                f"{outcomes[i].get('timestamp_utc')} | "
                f"{outcomes[i].get('action')} | "
                f"correct={outcomes[i].get('correct')} | "
                f"future_bad={outcomes[i].get('future_bad')}"
            ),
        )

        selected = outcomes[selected_index]

        d1, d2, d3, d4 = st.columns(4)

        with d1:
            st.metric("Action", selected.get("action"))

        with d2:
            st.metric("Risk State", selected.get("risk_state"))

        with d3:
            st.metric("Correct?", str(selected.get("correct")))

        with d4:
            st.metric("Future Bad?", str(selected.get("future_bad")))

        d5, d6, d7 = st.columns(3)

        with d5:
            st.metric("Future Bad Count", selected.get("future_bad_count"))

        with d6:
            st.metric("Confidence", selected.get("confidence"))

        with d7:
            st.metric("Avoided Risk", selected.get("avoided_risk_exposure"))

        st.markdown("### Reason")
        st.write(selected.get("reason"))

        st.markdown("### Raw Outcome JSON")
        st.json(selected)

    st.caption(f"Last dashboard refresh: {datetime.now(timezone.utc).isoformat()}")

except Exception as exc:
    st.error("Failed to fetch decision outcomes from API.")
    st.code(str(exc))
    st.warning(f"Make sure API is reachable at `{API_URL}` and `decision_outcomes.csv` exists.")
