from __future__ import annotations

import csv
import json
import os
from typing import Any

import pandas as pd

HISTORY_FIELDS = [
    "timestamp",
    "mode",
    "latest_block",
    "window_size",
    "threshold",
    "dij",
    "regime",
    "mean_tx_count",
    "std_tx_count",
    "gas_dij",
    "base_fee_dij",
    "note",
]

ALERT_FIELDS = [
    "timestamp",
    "mode",
    "latest_block",
    "threshold",
    "dij",
    "regime",
    "message",
    "event_type",      # started / cleared / info
    "alert_id",        # optional unique id for paired alert lifecycle
    "is_active",       # True/False snapshot
]

DEFAULT_ALERT_STATE = {
    "is_active": False,
    "alert_id": None,
    "started_at": None,
    "started_block": None,
    "last_dij": None,
    "last_regime": None,
    "last_message": None,
}


def ensure_data_dir(data_dir: str) -> None:
    os.makedirs(data_dir, exist_ok=True)


def _append_row(file_path: str, fieldnames: list[str], row: dict[str, Any]) -> None:
    file_exists = os.path.exists(file_path)

    with open(file_path, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        clean_row = {field: row.get(field, "") for field in fieldnames}
        writer.writerow(clean_row)


def _safe_read_csv(file_path: str, columns: list[str]) -> pd.DataFrame:
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=columns)

    try:
        return pd.read_csv(file_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)


def _alert_state_path(data_dir: str) -> str:
    return os.path.join(data_dir, "alert_state.json")


def _history_path(data_dir: str) -> str:
    return os.path.join(data_dir, "history.csv")


def _alerts_path(data_dir: str) -> str:
    return os.path.join(data_dir, "alerts.csv")


# -----------------------------
# History
# -----------------------------
def append_history(data_dir: str, row: dict[str, Any]) -> None:
    ensure_data_dir(data_dir)
    _append_row(_history_path(data_dir), HISTORY_FIELDS, row)


def load_history(data_dir: str) -> pd.DataFrame:
    ensure_data_dir(data_dir)
    return _safe_read_csv(_history_path(data_dir), HISTORY_FIELDS)


def get_latest_history_row(data_dir: str, mode: str | None = None) -> dict[str, Any] | None:
    df = load_history(data_dir)

    if df.empty:
        return None

    if mode is not None and "mode" in df.columns:
        df = df[df["mode"] == mode]

    if df.empty:
        return None

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")

    return df.iloc[-1].to_dict()


# -----------------------------
# Alerts
# -----------------------------
def append_alert(data_dir: str, row: dict[str, Any]) -> None:
    ensure_data_dir(data_dir)

    enriched_row = {
        "event_type": row.get("event_type", "info"),
        "is_active": row.get("is_active", ""),
        **row,
    }

    _append_row(_alerts_path(data_dir), ALERT_FIELDS, enriched_row)


def load_alerts(data_dir: str) -> pd.DataFrame:
    ensure_data_dir(data_dir)
    return _safe_read_csv(_alerts_path(data_dir), ALERT_FIELDS)


def get_latest_alert_row(data_dir: str, mode: str | None = None) -> dict[str, Any] | None:
    df = load_alerts(data_dir)

    if df.empty:
        return None

    if mode is not None and "mode" in df.columns:
        df = df[df["mode"] == mode]

    if df.empty:
        return None

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")

    return df.iloc[-1].to_dict()


# -----------------------------
# Alert state
# -----------------------------
def load_alert_state(data_dir: str) -> dict[str, Any]:
    ensure_data_dir(data_dir)
    state_path = _alert_state_path(data_dir)

    if not os.path.exists(state_path):
        return {}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_alert_state(data_dir: str, state: dict[str, Any]) -> None:
    ensure_data_dir(data_dir)
    state_path = _alert_state_path(data_dir)

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def get_mode_alert_state(data_dir: str, mode: str) -> dict[str, Any]:
    all_state = load_alert_state(data_dir)
    mode_state = all_state.get(mode, {}).copy()

    merged = DEFAULT_ALERT_STATE.copy()
    merged.update(mode_state)
    return merged


def set_mode_alert_state(data_dir: str, mode: str, state_update: dict[str, Any]) -> dict[str, Any]:
    all_state = load_alert_state(data_dir)
    current = DEFAULT_ALERT_STATE.copy()
    current.update(all_state.get(mode, {}))
    current.update(state_update)

    all_state[mode] = current
    save_alert_state(data_dir, all_state)
    return current


def clear_mode_alert_state(data_dir: str, mode: str) -> dict[str, Any]:
    cleared = DEFAULT_ALERT_STATE.copy()
    all_state = load_alert_state(data_dir)
    all_state[mode] = cleared
    save_alert_state(data_dir, all_state)
    return cleared


# -----------------------------
# Convenience helpers for next-stage alert lifecycle
# -----------------------------
def start_alert(
    data_dir: str,
    *,
    mode: str,
    timestamp: str,
    latest_block: int,
    threshold: float,
    dij: float,
    regime: str,
    message: str,
    alert_id: str,
) -> dict[str, Any]:
    state = set_mode_alert_state(
        data_dir,
        mode,
        {
            "is_active": True,
            "alert_id": alert_id,
            "started_at": timestamp,
            "started_block": latest_block,
            "last_dij": dij,
            "last_regime": regime,
            "last_message": message,
        },
    )

    append_alert(
        data_dir,
        {
            "timestamp": timestamp,
            "mode": mode,
            "latest_block": latest_block,
            "threshold": threshold,
            "dij": dij,
            "regime": regime,
            "message": message,
            "event_type": "started",
            "alert_id": alert_id,
            "is_active": True,
        },
    )

    return state


def update_active_alert(
    data_dir: str,
    *,
    mode: str,
    dij: float,
    regime: str,
    message: str | None = None,
) -> dict[str, Any]:
    current = get_mode_alert_state(data_dir, mode)
    updated = {
        "last_dij": dij,
        "last_regime": regime,
        "last_message": message or current.get("last_message"),
    }
    return set_mode_alert_state(data_dir, mode, updated)


def end_alert(
    data_dir: str,
    *,
    mode: str,
    timestamp: str,
    latest_block: int,
    threshold: float,
    dij: float,
    regime: str,
    message: str,
) -> dict[str, Any]:
    current = get_mode_alert_state(data_dir, mode)
    alert_id = current.get("alert_id")

    append_alert(
        data_dir,
        {
            "timestamp": timestamp,
            "mode": mode,
            "latest_block": latest_block,
            "threshold": threshold,
            "dij": dij,
            "regime": regime,
            "message": message,
            "event_type": "cleared",
            "alert_id": alert_id,
            "is_active": False,
        },
    )

    return clear_mode_alert_state(data_dir, mode)