from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/counterfactual_value_analysis.csv")

st.set_page_config(
    page_title="Counterfactual Value Analysis",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Counterfactual Value Analysis")
st.caption("Compares the system policy against a do-nothing full-exposure baseline.")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v, default=0.0):
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


rows = load_rows(DATA)

if not rows:
    st.info("No counterfactual rows yet. Run live.counterfactual_value_analysis first.")
    st.stop()

total = len(rows)
policy_better = sum(1 for r in rows if r.get("counterfactual_label") == "POLICY_BETTER_THAN_BASELINE")
baseline_better = sum(1 for r in rows if r.get("counterfactual_label") == "BASELINE_BETTER_THAN_POLICY")
roughly_equal = sum(1 for r in rows if r.get("counterfactual_label") == "ROUGHLY_EQUAL")

loss_avoided = sum(fnum(r.get("loss_avoided_proxy")) for r in rows)
opportunity_cost = sum(fnum(r.get("opportunity_cost_proxy")) for r in rows)
net_advantage = sum(fnum(r.get("net_policy_advantage")) for r in rows)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Counterfactual Events", total)

with c2:
    st.metric("Policy Better", policy_better)

with c3:
    st.metric("Baseline Better", baseline_better)

with c4:
    st.metric("Roughly Equal", roughly_equal)

c5, c6, c7 = st.columns(3)

with c5:
    st.metric("Loss Avoided Proxy", f"{loss_avoided:.4f}")

with c6:
    st.metric("Opportunity Cost Proxy", f"{opportunity_cost:.4f}")

with c7:
    st.metric("Net Policy Advantage", f"{net_advantage:.4f}")

st.divider()

st.subheader("Counterfactual Label Counts")
label_counts = {}
for r in rows:
    label = r.get("counterfactual_label", "UNKNOWN")
    label_counts[label] = label_counts.get(label, 0) + 1

st.dataframe(
    [{"label": k, "count": v} for k, v in label_counts.items()],
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Counterfactual Rows")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Counterfactual Result")
st.json(rows[-1])
