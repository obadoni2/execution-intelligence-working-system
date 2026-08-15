import csv
from pathlib import Path
import streamlit as st

DATA = Path(
    "live/data/policy_approval_deployment.csv"
)

st.set_page_config(
    page_title="Policy Approval",
    page_icon="🚀",
    layout="wide",
)

st.title(
    "🚀 Policy Approval & Deployment"
)

if not DATA.exists():
    st.info(
        "Run policy_approval_deployment first."
    )
    st.stop()

with DATA.open(
    "r",
    newline="",
    encoding="utf-8",
) as f:
    rows = list(csv.DictReader(f))

row = rows[-1]

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Stage",
        row["deployment_stage"],
    )

with c2:
    st.metric(
        "Capital %",
        row["capital_percentage"],
    )

with c3:
    st.metric(
        "Approval",
        row["approval_status"],
    )

with c4:
    st.metric(
        "Trust",
        row["trust_label"],
    )

st.divider()

st.json(row)
