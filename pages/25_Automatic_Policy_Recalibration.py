from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/automatic_policy_recalibration.csv")

st.set_page_config(
    page_title="Automatic Policy Recalibration",
    page_icon="🛠️",
    layout="wide",
)

st.title("🛠️ Automatic Policy Recalibration")
st.caption("Proposes safe policy changes based on trust, drift, regime performance, and counterfactual evidence.")


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
    st.info("No recalibration recommendations yet. Run live.automatic_policy_recalibration first.")
    st.stop()

total = len(rows)
recommended = sum(1 for r in rows if r.get("recommended_update") != "NO_CHANGE")
insufficient = sum(1 for r in rows if r.get("recalibration_status") == "INSUFFICIENT_DATA")
not_trusted = sum(1 for r in rows if r.get("recalibration_status") == "NOT_TRUSTED_FOR_UPDATE")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Policy Segments", total)

with c2:
    st.metric("Updates Suggested", recommended)

with c3:
    st.metric("Insufficient Data", insufficient)

with c4:
    st.metric("Not Trusted", not_trusted)

st.divider()

st.subheader("Recalibration Recommendations")

table = []
for r in rows:
    table.append({
        "environment": r.get("environment_bucket"),
        "decision": r.get("risk_decision"),
        "samples": r.get("samples"),
        "trust": r.get("policy_trust_label"),
        "trust_score": fnum(r.get("policy_trust_score")),
        "drift_score": fnum(r.get("drift_score")),
        "robustness_score": fnum(r.get("robustness_score")),
        "current_size": fnum(r.get("current_size_multiplier")),
        "proposed_size": fnum(r.get("proposed_size_multiplier")),
        "status": r.get("recalibration_status"),
        "update": r.get("recommended_update"),
        "reason": r.get("reason"),
    })

st.dataframe(table, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Recommendation")
st.json(rows[-1])

st.divider()

st.subheader("Raw Recalibration Rows")
st.dataframe(rows, use_container_width=True, hide_index=True)
