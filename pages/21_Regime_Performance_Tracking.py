from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/regime_performance_tracking.csv")

st.set_page_config(
    page_title="Regime Performance Tracking",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Regime Performance Tracking")
st.caption("Measures which execution policies remain reliable across market regimes.")


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
    st.info("No regime performance rows yet. Run live.regime_performance_tracker first.")
    st.stop()

total_samples = sum(int(fnum(r.get("samples"))) for r in rows)
best = max(rows, key=lambda r: fnum(r.get("robustness_score")))
worst = min(rows, key=lambda r: fnum(r.get("robustness_score")))

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Environment Groups", len(rows))

with c2:
    st.metric("Total Samples", total_samples)

with c3:
    st.metric("Best Policy", f"{best.get('environment_bucket')} / {best.get('risk_decision')}")

with c4:
    st.metric("Best Score", f"{fnum(best.get('robustness_score')):.3f}")

st.divider()

st.subheader("Regime Performance Table")

table = sorted(rows, key=lambda r: fnum(r.get("robustness_score")), reverse=True)
st.dataframe(table, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Worst Performing Policy Environment")
st.json(worst)
