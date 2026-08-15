from __future__ import annotations

import csv
from pathlib import Path

import streamlit as st


DATA_PATH = Path("live/data/gateio_market_snapshots.csv")

st.set_page_config(
    page_title="Gate.io Live Market Data",
    page_icon="🟢",
    layout="wide",
)

st.title("🟢 Gate.io Live Market Data")
st.caption("Public live multi-coin market-data ingestion. No trading keys. No live orders.")


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


rows = load_rows(DATA_PATH)

if not rows:
    st.warning("No Gate.io market snapshots found yet.")
    st.stop()

latest_by_symbol = {}
for row in rows:
    latest_by_symbol[row["symbol"]] = row

latest_rows = list(latest_by_symbol.values())

st.subheader("Live Market Overview")

cols = st.columns(4)
cols[0].metric("Coins Tracked", len(latest_rows))
cols[1].metric("Exchange", "Gate.io")
cols[2].metric("Snapshots", len(rows))
cols[3].metric("Mode", "Market Data Only")

st.divider()

st.subheader("Coin Cards")

for i in range(0, len(latest_rows), 4):
    cards = st.columns(4)

    for col, row in zip(cards, latest_rows[i:i+4]):
        with col:
            symbol = row.get("symbol", "")
            last = fnum(row.get("ticker_last"))
            spread = fnum(row.get("spread_bps"))
            depth = fnum(row.get("top_depth"))
            change = fnum(row.get("percentage_change"))

            st.markdown(
                f"""
                <div style="
                    padding:18px;
                    border-radius:18px;
                    border:1px solid rgba(255,255,255,0.12);
                    background:rgba(255,255,255,0.04);
                    margin-bottom:14px;
                ">
                    <h3 style="margin:0;">{symbol}</h3>
                    <p style="font-size:28px;margin:8px 0;"><b>{last:,.4f}</b></p>
                    <p>Spread: <b>{spread:.4f} bps</b></p>
                    <p>Top Depth: <b>{depth:,.4f}</b></p>
                    <p>24h Change: <b>{change:.2f}%</b></p>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.divider()

st.subheader("Live Market Table")

table_rows = []
for row in latest_rows:
    table_rows.append({
        "symbol": row.get("symbol"),
        "last": fnum(row.get("ticker_last")),
        "spread_bps": fnum(row.get("spread_bps")),
        "top_depth": fnum(row.get("top_depth")),
        "trade_count_100": row.get("trade_count_100"),
        "buy_trades_100": row.get("buy_trades_100"),
        "sell_trades_100": row.get("sell_trades_100"),
        "24h_change_%": fnum(row.get("percentage_change")),
        "provider_hash": row.get("provider_data_hash"),
    })

st.dataframe(table_rows, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Latest Raw Snapshot")
st.json(latest_rows[-1])

st.subheader("Recent Snapshot History")
st.dataframe(rows[-200:], use_container_width=True, hide_index=True)
