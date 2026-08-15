from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("SUPT_API_URL", "http://eth-monitor-api:8000")

st.set_page_config(
    page_title="SPY Lead-Lag Hardening",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 SPY Lead-Lag Hardening")
st.caption("Null-distribution and conditional forecasting tests for SPY early-warning claims.")


def fetch_json(path: str) -> dict:
    url = f"{API_URL}{path}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


try:
    payload = fetch_json("/v1/spy-lead-lag-hardening?n_shuffles=200&horizon_rows=30")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Total Rows", payload.get("total_rows"))

    with c2:
        st.metric("Threshold", payload.get("threshold"))

    with c3:
        st.metric("Source", payload.get("source_file"))

    st.divider()

    st.subheader("Observed vs Null Comparison")

    comparison = payload.get("comparison", {})
    comparison_rows = []

    for channel, data in comparison.items():
        comparison_rows.append(
            {
                "channel": channel,
                "observed_lead_rate": round(float(data.get("observed_lead_rate", 0)) * 100, 2),
                "null_mean_lead_rate": round(float(data.get("null_mean_lead_rate", 0)) * 100, 2),
                "lift_vs_null": data.get("lead_rate_lift_vs_null"),
                "observed_max_lead": data.get("observed_max_lead"),
                "null_p95_max_lead": data.get("null_p95_max_lead"),
                "exceeds_null_p95": data.get("max_lead_exceeds_null_p95"),
                "p_stress_given_cross": round(float(data.get("p_composite_stress_given_channel_cross", 0)) * 100, 2),
            }
        )

    st.dataframe(comparison_rows, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Key Interpretation")

    quote = comparison.get("quote_trade_ratio", {})
    if quote.get("max_lead_exceeds_null_p95"):
        st.success(
            "Quote/trade ratio produced an extreme-tail precursor: observed max lead exceeded shuffled-null p95."
        )
    else:
        st.info(
            "No channel max lead exceeded shuffled-null p95 in this run."
        )

    st.warning(
        "Average lead-frequency is not stronger than null in this run. The stronger signal is conditional forecasting and the quote/trade tail event."
    )

    st.divider()

    st.subheader("Conditional Forecasting")

    conditional = payload.get("conditional_forecast", {}).get("channels", {})
    conditional_rows = []

    for channel, data in conditional.items():
        conditional_rows.append(
            {
                "channel": channel,
                "channel_cross_count": data.get("channel_cross_count"),
                "future_composite_cross_hits": data.get("future_composite_cross_hits"),
                "p_composite_stress_given_channel_cross": round(
                    float(data.get("p_composite_stress_given_channel_cross", 0)) * 100,
                    2,
                ),
                "median_rows_to_composite": data.get("median_rows_to_composite"),
                "mean_rows_to_composite": data.get("mean_rows_to_composite"),
                "max_rows_to_composite": data.get("max_rows_to_composite"),
            }
        )

    st.dataframe(conditional_rows, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Raw JSON")
    st.json(payload)

except Exception as exc:
    st.error("Failed to fetch SPY lead-lag hardening.")
    st.code(str(exc))
