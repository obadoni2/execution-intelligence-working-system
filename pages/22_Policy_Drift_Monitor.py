from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/policy_drift_monitor.csv")

st.set_page_config(
    page_title="Policy Drift Monitor",
    page_icon="🧭",
    layout="wide",
)

st.title("🧭 Policy Drift Monitor")
st.caption("Detects policy degradation, insufficient evidence, and recalibration need.")


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
    st.info("No policy drift monitor data yet. Run live.policy_drift_monitor first.")
    st.stop()

row = rows[-1]

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Policy Status", row.get("policy_status"))

with c2:
    st.metric("Drift Score", row.get("drift_score"))

with c3:
    st.metric("Recommendation", row.get("recalibration_recommendation"))

with c4:
    st.metric("Total Events", row.get("total_events"))

c5, c6, c7 = st.columns(3)

with c5:
    st.metric("Policy Better Rate", f"{fnum(row.get('policy_better_rate')) * 100:.2f}%")

with c6:
    st.metric("Baseline Better Rate", f"{fnum(row.get('baseline_better_rate')) * 100:.2f}%")

with c7:
    st.metric("Avg Policy Value", f"{fnum(row.get('avg_policy_value')):.4f}")

st.divider()

st.subheader("Interpretation")
st.write(row.get("reason"))

st.divider()

st.subheader("Raw Drift Monitor Row")
st.json(row)
