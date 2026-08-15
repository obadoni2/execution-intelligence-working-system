from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/evidence_confidence_engine.csv")

st.set_page_config(
    page_title="Evidence Confidence Engine",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 Evidence Confidence Engine")
st.caption("Measures how much the system should trust its current policy-health conclusion.")


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
    st.info("No evidence confidence data yet. Run live.evidence_confidence_engine first.")
    st.stop()

row = rows[-1]

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Confidence", row.get("evidence_confidence_label"))

with c2:
    st.metric("Confidence Score", f"{fnum(row.get('evidence_confidence_score')):.3f}")

with c3:
    st.metric("Learning Status", row.get("learning_status"))

with c4:
    st.metric("Total Events", row.get("total_events"))

c5, c6, c7, c8 = st.columns(4)

with c5:
    st.metric("Completed Outcomes", row.get("completed_outcomes"))

with c6:
    st.metric("Symbol Coverage", row.get("symbol_coverage"))

with c7:
    st.metric("Regime Coverage", row.get("regime_coverage"))

with c8:
    st.metric("Drift Score", row.get("drift_score"))

st.divider()

st.subheader("Evidence Components")

components = [
    {"component": "Sample Size", "score": fnum(row.get("sample_score"))},
    {"component": "Outcome Completion", "score": fnum(row.get("completion_score"))},
    {"component": "Symbol Coverage", "score": fnum(row.get("symbol_score"))},
    {"component": "Regime Coverage", "score": fnum(row.get("regime_score"))},
    {"component": "Drift Consistency", "score": fnum(row.get("drift_consistency_score"))},
]

st.dataframe(components, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Interpretation")
st.write(row.get("interpretation"))

st.divider()

st.subheader("Raw Confidence Row")
st.json(row)
