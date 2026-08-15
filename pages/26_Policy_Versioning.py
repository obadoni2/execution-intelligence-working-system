from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/policy_versions.csv")

st.set_page_config(
    page_title="Policy Versioning",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 Policy Versioning & Safe Deployment")
st.caption("Tracks policy versions, deployment stages, approval requirements, and rollback rules.")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


rows = load_rows(DATA)

if not rows:
    st.info("No policy versions yet. Run live.policy_versioning first.")
    st.stop()

latest = rows[-1]

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Latest Policy", latest.get("policy_id"))

with c2:
    st.metric("Stage", latest.get("deployment_stage"))

with c3:
    st.metric("Trust", latest.get("trust_label"))

with c4:
    st.metric("Approval Required", latest.get("approval_required"))

st.divider()

st.subheader("Latest Policy Version")
st.json(latest)

st.divider()

st.subheader("Policy Version Registry")
st.dataframe(rows, use_container_width=True, hide_index=True)
