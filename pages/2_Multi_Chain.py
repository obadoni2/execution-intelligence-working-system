from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from supt_multichain import run_snapshot, snapshot_to_dict


st.set_page_config(
    page_title="SUPT Multi-Chain Monitor",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 SUPT Multi-Chain Monitor")
st.caption("Read-only multi-chain substrate observation layer. Not connected to execution decisions yet.")

with st.sidebar:
    st.header("Settings")
    window_size = st.slider("Window size", min_value=10, max_value=150, value=50, step=10)
    run_button = st.button("Refresh Multi-Chain Snapshot", type="primary")

st.warning(
    "Multi-chain state is currently read-only. It is not influencing the Ethereum decision API yet."
)

if run_button:
    with st.spinner("Fetching Ethereum, Base, Bitcoin, and Solana state..."):
        snapshot = run_snapshot(window_size=window_size)
        data = snapshot_to_dict(snapshot)

    st.success("Multi-chain snapshot updated.")
else:
    with st.spinner("Loading latest multi-chain snapshot..."):
        snapshot = run_snapshot(window_size=window_size)
        data = snapshot_to_dict(snapshot)

st.subheader("Cross-Chain Divergence")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Divergence", data.get("cross_chain_divergence"))

with col2:
    st.metric("Divergence Regime", data.get("divergence_regime"))

with col3:
    st.metric("Updated UTC", datetime.now(timezone.utc).strftime("%H:%M:%S"))

st.divider()

chains = [
    ("Ethereum", data.get("ethereum")),
    ("Base", data.get("base")),
    ("Bitcoin", data.get("bitcoin")),
    ("Solana", data.get("solana")),
]

cols = st.columns(4)

for col, (name, chain_data) in zip(cols, chains):
    with col:
        st.subheader(name)

        if chain_data is None:
            st.error("Probe failed")
            continue

        st.metric("Regime", chain_data.get("regime"))
        st.metric("d_ij", chain_data.get("d_ij"))
        st.metric(chain_data.get("metric_name", "metric"), chain_data.get("metric_value"))
        st.caption(f"Height / Slot: {chain_data.get('height')}")
        st.caption(chain_data.get("notes", ""))

st.divider()

st.subheader("Raw Snapshot JSON")

st.json(data)

st.info(
    "Next validation target: collect multi-chain observations over live sessions and test whether "
    "cross-chain divergence improves Ethereum transition timing beyond Ethereum-only signals."
)
