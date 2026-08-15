from __future__ import annotations

import csv
import json
from pathlib import Path

import streamlit as st


GUIDANCE_JSON = Path("equities/data/spy_execution_guidance.json")
PROBE_CSV = Path("equities/data/spy_probe_output.csv")
SUMMARY_CSV = Path("equities/data/spy_eval_summary.csv")


st.set_page_config(
    page_title="SPY Experimental Substrate Test",
    page_icon="📈",
    layout="wide",
)

st.title("📈 SPY Experimental Substrate Test")
st.caption("Separate equities research layer. Not connected to Ethereum production execution API.")

st.warning(
    "This page is experimental. SPY guidance is not production-calibrated and should not be treated as trading advice."
)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


guidance = load_json(GUIDANCE_JSON)
summary_rows = load_csv(SUMMARY_CSV)
probe_rows = load_csv(PROBE_CSV)

st.subheader("Current SPY Experimental Guidance")

if not guidance:
    st.error("No SPY guidance found. Run `python3 equities/spy_execution_guidance.py` first.")
else:
    action = guidance.get("recommended_action")

    if action == "PAUSE":
        st.error(f"Recommended Action: {action}")
    elif action in {"REDUCE_SIZE", "SELECTIVE_EXECUTE"}:
        st.warning(f"Recommended Action: {action}")
    else:
        st.success(f"Recommended Action: {action}")

    st.markdown(f"### {guidance.get('operator_guidance')}")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Risk State", guidance.get("risk_state"))

    with c2:
        st.metric("Can Execute Now?", str(guidance.get("can_execute_now")))

    with c3:
        st.metric("Max Size", f"{float(guidance.get('max_position_multiplier', 0.0)):.2f}x")

    with c4:
        st.metric("Composite d_ij", guidance.get("composite_d_ij"))

    c5, c6, c7, c8 = st.columns(4)

    with c5:
        st.metric("Spread d_ij", guidance.get("spread_d_ij"))

    with c6:
        st.metric("Depth d_ij", guidance.get("depth_d_ij"))

    with c7:
        st.metric("QU/TU d_ij", guidance.get("quote_trade_ratio_d_ij"))

    with c8:
        st.metric("Divergence", guidance.get("divergence"))

    st.divider()
    st.subheader("Raw SPY Guidance JSON")
    st.json(guidance)

st.divider()

st.subheader("SPY Evaluation Summary")

if summary_rows:
    st.dataframe(summary_rows, use_container_width=True, hide_index=True)
else:
    st.info("No SPY summary found yet.")

st.divider()

st.subheader("Recent SPY Probe Rows")

if probe_rows:
    st.dataframe(probe_rows[-50:], use_container_width=True, hide_index=True)
else:
    st.info("No SPY probe output found yet.")
