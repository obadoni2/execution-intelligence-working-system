from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.config import AppConfig
from app.live_eth import EthereumMonitorClient, extract_metric_series
from app.regime import classify_regime, regime_description
from app.simulator import advance_simulation, initialize_simulation
from app.storage import (
    append_history,
    end_alert,
    get_latest_history_row,
    get_mode_alert_state,
    load_alerts,
    load_history,
    start_alert,
    update_active_alert,
)
from app.supt import calculate_supt_dij, summarize_series

config = AppConfig.from_env()


def _provider_label(url: str) -> str:
    if not url:
        return "N/A"
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return url


st.set_page_config(
    page_title="ETH Congestion Monitor",
    page_icon="📈",
    layout="wide",
)

st.title("Ethereum Congestion Monitor")
st.caption("SUPT d_ij prototype monitor with simulation mode and optional live Ethereum mode.")

with st.sidebar:
    st.header("Controls")

    default_mode_index = 0 if config.mode == "simulation" else 1
    mode = st.selectbox("Mode", ["simulation", "live"], index=default_mode_index)

    window_size = int(
        st.number_input(
            "Rolling window size",
            min_value=20,
            max_value=500,
            value=config.window_size,
            step=10,
        )
    )

    threshold = float(
        st.number_input(
            "Alert threshold",
            min_value=0.1,
            max_value=5.0,
            value=float(config.alert_threshold),
            step=0.1,
        )
    )

    auto_refresh = st.checkbox("Auto refresh", value=True)
    refresh_interval_ms = int(
        st.number_input(
            "Refresh interval (ms)",
            min_value=2000,
            max_value=60000,
            value=config.refresh_interval_ms,
            step=1000,
        )
    )

    fallback_to_simulation = st.checkbox("Fallback to simulation if live fails", value=True)
    manual_advance = st.button("Advance one step")

refresh_count = 0
if auto_refresh:
    refresh_count = st_autorefresh(interval=refresh_interval_ms, key="eth-monitor-refresh")

# -----------------------------
# Data source selection
# -----------------------------
tx_counts: list[float] = []
block_numbers: list[int] = []
gas_used: list[float] = []
base_fee_gwei: list[float] = []
latest_block = 0
note = ""
requested_window = window_size
effective_window = window_size
mode_note = ""
active_rpc_provider = ""
providers_seen_in_window: list[str] = []

if mode == "simulation":
    if (
        "simulation_state" not in st.session_state
        or st.session_state.get("simulation_window_size") != window_size
    ):
        st.session_state["simulation_state"] = initialize_simulation(window_size)
        st.session_state["simulation_window_size"] = window_size
        st.session_state["last_refresh_count"] = refresh_count
    else:
        should_advance = False

        if manual_advance:
            should_advance = True
        elif auto_refresh and st.session_state.get("last_refresh_count") != refresh_count:
            should_advance = True

        if should_advance:
            st.session_state["simulation_state"] = advance_simulation(
                st.session_state["simulation_state"],
                window_size,
            )
            st.session_state["last_refresh_count"] = refresh_count

    simulation_state = st.session_state["simulation_state"]
    tx_counts = [float(x) for x in simulation_state["tx_counts"]]
    latest_block = int(simulation_state["latest_block"])
    block_numbers = list(range(latest_block - len(tx_counts) + 1, latest_block + 1))
    note = "Simulation mode"
    mode_note = "Using simulated transaction-count data."
    active_rpc_provider = "simulation"
    providers_seen_in_window = ["simulation"]

else:
    rpc_urls = getattr(config, "rpc_urls", None)
    if rpc_urls:
        client = EthereumMonitorClient(rpc_urls=rpc_urls)
    else:
        client = EthereumMonitorClient(getattr(config, "eth_rpc_url", ""))

    effective_window = client.get_effective_window(window_size)

    blocks, error = client.fetch_recent_blocks(window_size)

    if error is not None:
        if fallback_to_simulation:
            st.warning(f"Live mode failed: {error} — falling back to simulation mode.")
            if (
                "simulation_state" not in st.session_state
                or st.session_state.get("simulation_window_size") != window_size
            ):
                st.session_state["simulation_state"] = initialize_simulation(window_size)
                st.session_state["simulation_window_size"] = window_size

            if manual_advance or auto_refresh:
                st.session_state["simulation_state"] = advance_simulation(
                    st.session_state["simulation_state"],
                    window_size,
                )

            simulation_state = st.session_state["simulation_state"]
            tx_counts = [float(x) for x in simulation_state["tx_counts"]]
            latest_block = int(simulation_state["latest_block"])
            block_numbers = list(range(latest_block - len(tx_counts) + 1, latest_block + 1))
            note = f"Fallback simulation after live failure: {error}"
            mode = "simulation"
            effective_window = window_size
            mode_note = "Live fetch failed; currently showing fallback simulation data."
            active_rpc_provider = "simulation"
            providers_seen_in_window = ["simulation"]
        else:
            st.error(f"Live mode failed: {error}")
            st.stop()
    else:
        metrics = extract_metric_series(blocks)
        tx_counts = metrics["tx_counts"]
        gas_used = metrics["gas_used"]
        base_fee_gwei = metrics["base_fee_gwei"]
        block_numbers = metrics["block_numbers"]
        latest_block = block_numbers[-1] if block_numbers else 0
        effective_window = len(tx_counts) if tx_counts else effective_window
        note = "Live Ethereum mode"

        providers_seen_in_window = sorted(
            {
                _provider_label(str(block.get("rpc_provider", "")))
                for block in blocks
                if block.get("rpc_provider")
            }
        )
        active_rpc_provider = _provider_label(getattr(client, "active_rpc_url", ""))

        if effective_window != requested_window:
            mode_note = (
                f"Live mode requested {requested_window} blocks, "
                f"but currently uses an effective window of {effective_window}."
            )
        else:
            mode_note = "Live Ethereum data is active."

if len(tx_counts) < 2:
    st.error("Not enough data to compute d_ij.")
    st.stop()

# -----------------------------
# Core calculations
# -----------------------------
current_dij = calculate_supt_dij(tx_counts, window_size=effective_window)
current_regime = classify_regime(current_dij)
tx_summary = summarize_series(tx_counts)

gas_dij = calculate_supt_dij(gas_used, window_size=effective_window) if len(gas_used) >= 2 else 0.0
base_fee_dij = (
    calculate_supt_dij(base_fee_gwei, window_size=effective_window) if len(base_fee_gwei) >= 2 else 0.0
)

# -----------------------------
# Logging and alert lifecycle
# -----------------------------
timestamp_now = datetime.now(timezone.utc).isoformat()

previous_row = get_latest_history_row(config.data_dir, mode=mode)
previous_dij = None
previous_latest_block = None

if previous_row is not None:
    try:
        previous_dij = float(previous_row.get("dij"))
    except Exception:
        previous_dij = None

    try:
        previous_latest_block = int(float(previous_row.get("latest_block")))
    except Exception:
        previous_latest_block = None

should_log = previous_latest_block != latest_block

current_alert_state = get_mode_alert_state(config.data_dir, mode)
alert_started = False
alert_cleared = False

if should_log:
    append_history(
        config.data_dir,
        {
            "timestamp": timestamp_now,
            "mode": mode,
            "latest_block": latest_block,
            "window_size": effective_window,
            "threshold": threshold,
            "dij": round(current_dij, 6),
            "regime": current_regime,
            "mean_tx_count": round(tx_summary["mean"], 4),
            "std_tx_count": round(tx_summary["std"], 4),
            "gas_dij": round(gas_dij, 6),
            "base_fee_dij": round(base_fee_dij, 6),
            "note": f"{note} | rpc={active_rpc_provider}",
        },
    )

    crossing_up = previous_dij is not None and previous_dij < threshold <= current_dij
    crossing_down = previous_dij is not None and previous_dij >= threshold > current_dij

    if crossing_up:
        alert_id = f"{mode}-{latest_block}"
        current_alert_state = start_alert(
            config.data_dir,
            mode=mode,
            timestamp=timestamp_now,
            latest_block=latest_block,
            threshold=threshold,
            dij=round(current_dij, 6),
            regime=current_regime,
            message=f"d_ij crossed above threshold {threshold:.2f}",
            alert_id=alert_id,
        )
        alert_started = True

    elif crossing_down and current_alert_state.get("is_active"):
        current_alert_state = end_alert(
            config.data_dir,
            mode=mode,
            timestamp=timestamp_now,
            latest_block=latest_block,
            threshold=threshold,
            dij=round(current_dij, 6),
            regime=current_regime,
            message=f"d_ij dropped back below threshold {threshold:.2f}",
        )
        alert_cleared = True

    elif current_dij >= threshold:
        if current_alert_state.get("is_active"):
            current_alert_state = update_active_alert(
                config.data_dir,
                mode=mode,
                dij=round(current_dij, 6),
                regime=current_regime,
                message="Alert remains active",
            )
        else:
            alert_id = f"{mode}-{latest_block}"
            current_alert_state = start_alert(
                config.data_dir,
                mode=mode,
                timestamp=timestamp_now,
                latest_block=latest_block,
                threshold=threshold,
                dij=round(current_dij, 6),
                regime=current_regime,
                message=f"d_ij is already above threshold {threshold:.2f} on observed state",
                alert_id=alert_id,
            )
            alert_started = True

    elif current_alert_state.get("is_active"):
        current_alert_state = end_alert(
            config.data_dir,
            mode=mode,
            timestamp=timestamp_now,
            latest_block=latest_block,
            threshold=threshold,
            dij=round(current_dij, 6),
            regime=current_regime,
            message=f"d_ij is below threshold {threshold:.2f}; alert cleared",
        )
        alert_cleared = True

current_alert_state = get_mode_alert_state(config.data_dir, mode)
alert_active = bool(current_alert_state.get("is_active", False))

# -----------------------------
# Load and filter data
# -----------------------------
history_df = load_history(config.data_dir)
alerts_df = load_alerts(config.data_dir)

if not history_df.empty:
    history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], errors="coerce")
    history_df = history_df.sort_values("timestamp")

if not alerts_df.empty:
    alerts_df["timestamp"] = pd.to_datetime(alerts_df["timestamp"], errors="coerce")
    alerts_df = alerts_df.sort_values("timestamp")

history_mode_df = history_df[history_df["mode"] == mode].copy() if not history_df.empty else pd.DataFrame()
alerts_mode_df = alerts_df[alerts_df["mode"] == mode].copy() if not alerts_df.empty else pd.DataFrame()

last_alert_time = None
if not alerts_mode_df.empty:
    last_alert_time = alerts_mode_df.iloc[-1]["timestamp"]

# -----------------------------
# Top status
# -----------------------------
if alert_active:
    st.error(
        f"Alert state: current d_ij is {current_dij:.4f}, which is at or above the threshold {threshold:.2f}."
    )
else:
    st.success(
        f"Current d_ij is {current_dij:.4f}, below the threshold {threshold:.2f}."
    )

if alert_started:
    st.warning("New alert started on this update.")

if alert_cleared:
    st.info("Alert cleared on this update.")

# -----------------------------
# Metrics
# -----------------------------
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("Current d_ij", f"{current_dij:.4f}")
metric_col2.metric("Regime", current_regime)
metric_col3.metric("Latest block", f"{latest_block}")
metric_col4.metric("Mean TX count", f"{tx_summary['mean']:.2f}")

metric_col5, metric_col6, metric_col7, metric_col8 = st.columns(4)
metric_col5.metric("TX count std", f"{tx_summary['std']:.2f}")
metric_col6.metric("Gas d_ij", f"{gas_dij:.4f}")
metric_col7.metric("Base fee d_ij", f"{base_fee_dij:.4f}")
metric_col8.metric("Effective window", f"{effective_window}")

status_col1, status_col2, status_col3, status_col4 = st.columns(4)
status_col1.metric("Requested window", f"{requested_window}")
status_col2.metric("Alert active", "Yes" if alert_active else "No")
status_col3.metric("Mode", mode.upper())
status_col4.metric("Alerts logged", f"{len(alerts_mode_df)}" if not alerts_mode_df.empty else "0")

st.markdown(f"**Regime meaning:** {regime_description(current_dij)}")
st.markdown(f"**Data source note:** {mode_note}")
st.markdown(f"**Run note:** {note}")
st.markdown(f"**Active RPC provider:** {active_rpc_provider}")
if providers_seen_in_window:
    st.markdown(f"**Providers seen in current window:** {', '.join(providers_seen_in_window)}")
st.markdown(f"**Last updated (UTC):** {timestamp_now}")

if current_alert_state.get("started_at"):
    st.markdown(f"**Current alert started at (UTC):** {current_alert_state['started_at']}")

if current_alert_state.get("started_block") is not None:
    st.markdown(f"**Current alert started block:** {current_alert_state['started_block']}")

if last_alert_time is not None:
    st.markdown(f"**Last alert event ({mode}):** {last_alert_time}")

# -----------------------------
# Charts
# -----------------------------
st.subheader("Rolling transaction counts")
tx_chart_df = pd.DataFrame(
    {
        "block_number": block_numbers,
        "tx_count": tx_counts,
    }
).set_index("block_number")
st.line_chart(tx_chart_df, width="stretch")

st.subheader("d_ij history")
if not history_mode_df.empty:
    history_plot_df = history_mode_df[["timestamp", "dij"]].copy()
    history_plot_df["threshold"] = threshold
    history_plot_df = history_plot_df.set_index("timestamp")
    st.line_chart(history_plot_df, width="stretch")
else:
    st.info(f"No {mode} history logged yet.")

# -----------------------------
# Tables
# -----------------------------
st.subheader(f"Recent alerts ({mode})")
if not alerts_mode_df.empty:
    alerts_view = alerts_mode_df.sort_values("timestamp", ascending=False).copy()
    st.dataframe(alerts_view.head(20), width="stretch")
else:
    st.info(f"No {mode} alerts logged yet.")

st.subheader(f"Latest monitor records ({mode})")
if not history_mode_df.empty:
    history_view = history_mode_df.sort_values("timestamp", ascending=False).copy()
    st.dataframe(history_view.head(20), width="stretch")
else:
    st.info(f"No {mode} history logged yet.")