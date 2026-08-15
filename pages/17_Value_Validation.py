from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/value_validation.csv")

st.set_page_config(
    page_title="Value Validation",
    page_icon="💰",
    layout="wide",
)

st.title("💰 Value Validation")
st.caption("Compares system intervention decisions against a do-nothing baseline.")


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
    st.info("No value validation rows yet. Run live.value_validation first.")
    st.stop()

total = len(rows)
positive = sum(1 for r in rows if r.get("value_label") == "POSITIVE_VALUE")
negative = sum(1 for r in rows if r.get("value_label") == "NEGATIVE_VALUE")
neutral = sum(1 for r in rows if r.get("value_label") == "NEUTRAL_VALUE")
net_value = sum(fnum(r.get("net_decision_value")) for r in rows)
avg_value = net_value / total if total else 0.0

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Value Events", total)

with c2:
    st.metric("Positive Rate", f"{positive / total * 100:.2f}%")

with c3:
    st.metric("Negative Rate", f"{negative / total * 100:.2f}%")

with c4:
    st.metric("Net Policy Value", f"{net_value:.3f}")

c5, c6 = st.columns(2)

with c5:
    st.metric("Average Value / Decision", f"{avg_value:.3f}")

with c6:
    st.metric("Neutral Events", neutral)

st.divider()

st.subheader("Value Labels")
label_counts = {}
for r in rows:
    label = r.get("value_label", "UNKNOWN")
    label_counts[label] = label_counts.get(label, 0) + 1

label_rows = [{"label": k, "count": v} for k, v in label_counts.items()]
st.dataframe(label_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Value Validation Rows")
st.dataframe(rows[-300:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Value Validation Result")
st.json(rows[-1])
