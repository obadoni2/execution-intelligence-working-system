from __future__ import annotations

import pandas as pd
import streamlit as st

from app.product_proof import build_product_proof, format_float, format_percent


st.set_page_config(
    page_title="SUPT Product Proof",
    page_icon="📊",
    layout="wide",
)

st.title("📊 SUPT Ethereum Agent — Product Proof")
st.caption(
    "Agent vs baseline counterfactual tracking for Ethereum execution-risk decisions."
)

proof = build_product_proof(data_dir="data")

counterfactual = proof["counterfactual"]
base_rate = proof["base_rate"]
episode_cards = proof["episode_cards"]

st.markdown("## 1. Agent vs Baseline")

if not counterfactual["available"]:
    st.warning(
        "No counterfactual evaluation found yet. Run "
        "`python scripts/evaluate_counterfactuals.py` first."
    )
else:
    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Evaluated Windows",
        f"{counterfactual['windows']:,}",
    )

    col2.metric(
        "Bad Exposure Reduction",
        format_percent(counterfactual["bad_exposure_reduction"]),
    )

    col3.metric(
        "Risk Exposure Reduction",
        format_percent(counterfactual["risk_exposure_reduction"]),
    )

    st.markdown("### Exposure Comparison")

    exposure_df = pd.DataFrame(
        [
            {
                "Metric": "Bad execution exposure",
                "Baseline": counterfactual["baseline_bad_exposure"],
                "Agent": counterfactual["agent_bad_exposure"],
                "Avoided": counterfactual["avoided_bad_exposure"],
                "Reduction": format_percent(counterfactual["bad_exposure_reduction"]),
            },
            {
                "Metric": "Future risk exposure",
                "Baseline": counterfactual["baseline_risk_exposure"],
                "Agent": counterfactual["agent_risk_exposure"],
                "Avoided": counterfactual["avoided_risk_exposure"],
                "Reduction": format_percent(counterfactual["risk_exposure_reduction"]),
            },
        ]
    )

    st.dataframe(exposure_df, use_container_width=True, hide_index=True)

st.divider()

st.markdown("## 2. Base-Rate Sanity Check")
st.caption(
    "This checks whether the agent is actually discriminating risk, "
    "not simply pausing too often."
)

if not base_rate["available"]:
    st.warning(
        "No base-rate check found yet. Run "
        "`python scripts/run_base_rate_check.py` first."
    )
else:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Windows", f"{base_rate['total_windows']:,}")
    col2.metric("Pause Rate", format_percent(base_rate["pause_rate"]))
    col3.metric("Discrimination Gap", format_percent(base_rate["discrimination_gap"]))
    col4.metric("Agent Accuracy", format_percent(base_rate["agent_accuracy"]))

    col5, col6, col7, col8 = st.columns(4)

    col5.metric("Bad When Paused", format_percent(base_rate["bad_rate_when_paused"]))
    col6.metric("Bad When Executed", format_percent(base_rate["bad_rate_when_executed"]))
    col7.metric("Unnecessary Pause Rate", format_percent(base_rate["unnecessary_pause_rate"]))
    col8.metric("Bad-Window Recall", format_percent(base_rate["bad_window_recall"]))

    verdict = base_rate["verdict"]

    if verdict == "strong_discrimination":
        st.success(f"Verdict: {verdict}")
    elif verdict == "promising_discrimination":
        st.info(f"Verdict: {verdict}")
    else:
        st.warning(f"Verdict: {verdict}")

    st.markdown("### 2×2 Truth Table")

    truth_table = pd.DataFrame(
        [
            {
                "Agent Decision": "PAUSE",
                "Future Bad": base_rate["pause_bad"],
                "Future Good": base_rate["pause_good"],
            },
            {
                "Agent Decision": "EXECUTE / REDUCE / RESUME",
                "Future Bad": base_rate["execute_bad"],
                "Future Good": base_rate["execute_good"],
            },
        ]
    )

    st.dataframe(truth_table, use_container_width=True, hide_index=True)

st.divider()

st.markdown("## 3. Episode-Level Avoided Windows")
st.caption(
    "Deduplicated demo cases: one representative case per stress episode."
)

if episode_cards.empty:
    st.warning(
        "No episode-level demo cards found yet. Run "
        "`python scripts/run_base_rate_check.py` after the counterfactual evaluator."
    )
else:
    for _, row in episode_cards.iterrows():
        case_id = int(row.get("case_id", 0))
        title = f"Case {case_id}: HIGH_STRESS → PAUSE avoided a bad window"

        with st.container(border=True):
            st.subheader(title)

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Start Block", int(row.get("start_block", 0)))
            col2.metric("Future Block", int(row.get("future_block", 0)))
            col3.metric("Horizon", f"{int(row.get('horizon_blocks', 0))} blocks")
            col4.metric("Agent Action", str(row.get("agent_action", "PAUSE")))

            col5, col6, col7 = st.columns(3)

            col5.metric("Future Gas d_ij", f"{float(row.get('future_gas_dij', 0.0)):.4f}")
            col6.metric(
                "Future Risk",
                f"{float(row.get('future_execution_risk_score', 0.0)):.4f}",
            )
            col7.metric(
                "Avoided Risk Exposure",
                f"{float(row.get('avoided_future_risk_exposure', 0.0)):.6f}",
            )

            st.markdown("**Plain-English read:**")
            st.write(row.get("plain_english", ""))

st.divider()

st.markdown("## Guardrail")
st.info(
    "This is proxy-based counterfactual evaluation, not live PnL. "
    "It compares an agent branch against a baseline branch using future gas, regime, "
    "and execution-risk conditions. Real metrics like gas paid, slippage, fill price vs mid, "
    "and transaction success rate can be attached later."
)

st.markdown("## Next Target")
st.write(
    "Keep the logger running until 1,000+ windows and 10+ distinct stress episodes, "
    "then re-run the evaluator and base-rate check."
)
