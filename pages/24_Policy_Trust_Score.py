from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/policy_trust_score.csv")

st.set_page_config(
    page_title="Policy Trust Score",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Policy Trust Score")
st.caption("Estimates whether the current policy has earned enough evidence to guide future decisions.")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


rows = load_rows(DATA)

if not rows:
    st.info("No policy trust score yet. Run live.policy_trust_score first.")
    st.stop()

row = rows[-1]

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Trust Label", row.get("policy_trust_label"))

with c2:
    st.metric("Trust Score", f"{fnum(row.get('policy_trust_score')):.3f}")

with c3:
    st.metric("Recommended Action", row.get("recommended_action"))

with c4:
    st.metric("Total Events", row.get("total_events"))

st.divider()

st.subheader("Trust Components")

components = [
    {"component": "Evidence Confidence", "score": fnum(row.get("evidence_confidence_score"))},
    {"component": "Drift Health", "score": fnum(row.get("drift_health_score"))},
    {"component": "Regime Score", "score": fnum(row.get("regime_score"))},
    {"component": "Counterfactual Score", "score": fnum(row.get("counterfactual_score"))},
    {"component": "Sample Size", "score": fnum(row.get("sample_score"))},
]

st.dataframe(components, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Policy Evidence Summary")

summary = {
    "policy_better": row.get("policy_better"),
    "baseline_better": row.get("baseline_better"),
    "roughly_equal": row.get("roughly_equal"),
    "net_policy_advantage": row.get("net_policy_advantage"),
    "avg_policy_advantage": row.get("avg_policy_advantage"),
    "regime_groups": row.get("regime_groups"),
    "positive_regimes": row.get("positive_regimes"),
    "negative_regimes": row.get("negative_regimes"),
}

st.json(summary)

st.divider()

st.subheader("Interpretation")
st.write(row.get("interpretation"))

st.divider()

st.subheader("Raw Trust Score Row")
st.json(row)
