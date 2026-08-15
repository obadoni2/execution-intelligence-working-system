from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/policy_learning_recommendations.csv")

st.set_page_config(
    page_title="Policy Learning Engine",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Policy Learning Engine")
st.caption("Learns cautious policy recommendations from counterfactual outcomes while penalizing low sample size.")


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
    st.info("No policy learning recommendations yet. Run live.policy_learning_engine first.")
    st.stop()

total = len(rows)
changed = sum(1 for r in rows if r.get("learned_action") not in {"KEEP_CURRENT_RULES", r.get("current_risk_decision")})
keep = sum(1 for r in rows if r.get("learned_action") == "KEEP_CURRENT_RULES")
high_conf = sum(1 for r in rows if r.get("learned_confidence") == "HIGH")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Symbols", total)

with c2:
    st.metric("Policy Changes Suggested", changed)

with c3:
    st.metric("Keep Current Rules", keep)

with c4:
    st.metric("High Confidence", high_conf)

st.divider()

st.subheader("Policy Recommendations")

table = []
for r in rows:
    table.append({
        "symbol": r.get("symbol"),
        "current_regime": r.get("current_regime"),
        "current_risk_decision": r.get("current_risk_decision"),
        "learned_action": r.get("learned_action"),
        "confidence": r.get("learned_confidence"),
        "score": fnum(r.get("learned_score")),
        "reason": r.get("learning_reason"),
        "stress_score": fnum(r.get("current_stress_score")),
        "spread_bps": fnum(r.get("spread_bps")),
        "top_depth": fnum(r.get("top_depth")),
    })

st.dataframe(table, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Raw Recommendation Rows")
st.dataframe(rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Recommendation")
st.json(rows[-1])
