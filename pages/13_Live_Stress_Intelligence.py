from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA = Path("live/data/live_stress_receipts.csv")

st.set_page_config(
    page_title="Live Stress Intelligence",
    page_icon="🔥",
    layout="wide",
)

st.title("🔥 Live Stress Intelligence")
st.caption("Multi-coin execution-risk scoring from live Gate.io market data. No live orders.")


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


def badge(regime: str) -> str:
    colors = {
        "NORMAL": "#16a34a",
        "CAUTION": "#ca8a04",
        "HIGH_STRESS": "#ea580c",
        "CRITICAL": "#dc2626",
    }
    return colors.get(regime, "#64748b")


rows = load_rows(DATA)

if not rows:
    st.warning("No live stress receipts found yet. Run live_regime_engine first.")
    st.stop()

latest = {}
for row in rows:
    latest[row["symbol"]] = row

latest_rows = sorted(
    latest.values(),
    key=lambda r: fnum(r.get("stress_score")),
    reverse=True,
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Coins Scored", len(latest_rows))

with c2:
    st.metric("Receipts", len(rows))

with c3:
    st.metric("Highest Stress", latest_rows[0].get("symbol"))

with c4:
    st.metric("Top Score", latest_rows[0].get("stress_score"))

st.divider()

st.subheader("Execution Stress Heatmap")

for i in range(0, len(latest_rows), 4):
    cols = st.columns(4)

    for col, row in zip(cols, latest_rows[i:i + 4]):
        regime = row.get("regime", "UNKNOWN")
        color = badge(regime)

        with col:
            st.markdown(
                f"""
                <div style="
                    padding:18px;
                    border-radius:18px;
                    border:1px solid rgba(255,255,255,0.12);
                    background:rgba(255,255,255,0.04);
                    border-left:8px solid {color};
                    margin-bottom:14px;
                ">
                    <h3 style="margin:0;">{row.get("symbol")}</h3>
                    <p style="font-size:22px;margin:8px 0;"><b>{regime}</b></p>
                    <p>Guidance: <b>{row.get("guidance")}</b></p>
                    <p>Stress Score: <b>{fnum(row.get("stress_score")):.4f}</b></p>
                    <p>Spread: <b>{fnum(row.get("spread_bps")):.4f} bps</b></p>
                    <p>Depth: <b>{fnum(row.get("top_depth")):.4f}</b></p>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.divider()

st.subheader("Symbol Ranking")

table_rows = []
for row in latest_rows:
    table_rows.append({
        "symbol": row.get("symbol"),
        "regime": row.get("regime"),
        "guidance": row.get("guidance"),
        "stress_score": fnum(row.get("stress_score")),
        "spread_bps": fnum(row.get("spread_bps")),
        "top_depth": fnum(row.get("top_depth")),
        "trade_imbalance": fnum(row.get("trade_imbalance")),
        "provider_hash": row.get("provider_data_hash"),
    })

st.dataframe(table_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Recent Live Stress Receipts")
st.dataframe(rows[-200:], use_container_width=True, hide_index=True)

st.divider()

st.subheader("Raw Highest-Stress Receipt")
st.json(latest_rows[0])
