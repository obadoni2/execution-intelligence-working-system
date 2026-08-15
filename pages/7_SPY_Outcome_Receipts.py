from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


RECEIPTS_PATH = Path("equities/data/spy_outcomes.csv")

st.set_page_config(
    page_title="SPY Outcome Receipts",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 SPY Outcome Receipts")
st.caption("Append-only SPY outcome ledger bound to the frozen schema hash.")

st.info(
    "This page reads the SPY receipt ledger directly. Outcomes are derived from frozen rules, not manually assigned."
)


def load_receipts(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        clean_lines = [line for line in f if not line.startswith("#")]

    return list(csv.DictReader(clean_lines))


rows = load_receipts(RECEIPTS_PATH)

if not rows:
    st.warning("No SPY outcome receipts found yet.")
    st.stop()

bad = [r for r in rows if r.get("is_bad") == "TRUE"]
clean = [r for r in rows if r.get("is_bad") == "FALSE"]

schema_hash = rows[0].get("schema_hash", "N/A")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Total Receipts", len(rows))

with c2:
    st.metric("Bad Receipts", len(bad))

with c3:
    st.metric("Clean Receipts", len(clean))

with c4:
    bad_rate = len(bad) / len(rows) if rows else 0
    st.metric("Bad Rate", f"{bad_rate * 100:.2f}%")

st.subheader("Frozen Schema Hash")
st.code(schema_hash)

st.divider()

st.subheader("Receipt Table")

table_rows = []
for r in rows:
    table_rows.append(
        {
            "window_id": r.get("window_id"),
            "decision_state": r.get("decision_state"),
            "regime_band": r.get("regime_band"),
            "composite_d_ij": r.get("composite_d_ij"),
            "is_bad": r.get("is_bad"),
            "n_rules_triggered": r.get("n_rules_triggered"),
            "triggered_rules": r.get("triggered_rules"),
            "provider": r.get("provider"),
            "provider_data_hash": r.get("provider_data_hash"),
        }
    )

st.dataframe(table_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Receipt Detail")

selected_index = st.selectbox(
    "Select receipt",
    options=list(range(len(rows))),
    format_func=lambda i: (
        f"{rows[i].get('window_id')} | "
        f"{rows[i].get('decision_state')} | "
        f"is_bad={rows[i].get('is_bad')}"
    ),
)

selected = rows[selected_index]

d1, d2, d3, d4 = st.columns(4)

with d1:
    st.metric("Decision State", selected.get("decision_state"))

with d2:
    st.metric("Regime Band", selected.get("regime_band"))

with d3:
    st.metric("Composite d_ij", selected.get("composite_d_ij"))

with d4:
    st.metric("Is Bad?", selected.get("is_bad"))

st.markdown("### Triggered Rules")
st.write(selected.get("triggered_rules") or "None")

st.markdown("### Provider Hash")
st.code(selected.get("provider_data_hash", ""))

st.markdown("### Raw Receipt")
st.json(selected)
