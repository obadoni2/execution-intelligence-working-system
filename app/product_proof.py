from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return int(float(value))
    except Exception:
        return default


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path)
        return df
    except Exception:
        return pd.DataFrame()


def _reduction(avoided: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0
    return avoided / baseline


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def build_counterfactual_summary(data_dir: str | Path = "data") -> dict[str, Any]:
    data_dir = Path(data_dir)
    eval_path = data_dir / "counterfactual_eval.csv"

    df = _load_csv(eval_path)

    if df.empty:
        return {
            "available": False,
            "windows": 0,
            "bad_exposure_reduction": 0.0,
            "risk_exposure_reduction": 0.0,
            "baseline_bad_exposure": 0.0,
            "agent_bad_exposure": 0.0,
            "avoided_bad_exposure": 0.0,
            "baseline_risk_exposure": 0.0,
            "agent_risk_exposure": 0.0,
            "avoided_risk_exposure": 0.0,
        }

    numeric_cols = [
        "baseline_bad_exposure",
        "agent_bad_exposure",
        "avoided_bad_exposure",
        "baseline_future_risk_exposure",
        "agent_future_risk_exposure",
        "avoided_future_risk_exposure",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    baseline_bad = float(df["baseline_bad_exposure"].sum())
    agent_bad = float(df["agent_bad_exposure"].sum())
    avoided_bad = float(df["avoided_bad_exposure"].sum())

    baseline_risk = float(df["baseline_future_risk_exposure"].sum())
    agent_risk = float(df["agent_future_risk_exposure"].sum())
    avoided_risk = float(df["avoided_future_risk_exposure"].sum())

    return {
        "available": True,
        "windows": len(df),
        "bad_exposure_reduction": _reduction(avoided_bad, baseline_bad),
        "risk_exposure_reduction": _reduction(avoided_risk, baseline_risk),
        "baseline_bad_exposure": baseline_bad,
        "agent_bad_exposure": agent_bad,
        "avoided_bad_exposure": avoided_bad,
        "baseline_risk_exposure": baseline_risk,
        "agent_risk_exposure": agent_risk,
        "avoided_risk_exposure": avoided_risk,
    }


def build_base_rate_summary(data_dir: str | Path = "data") -> dict[str, Any]:
    data_dir = Path(data_dir)
    path = data_dir / "base_rate_check.csv"

    df = _load_csv(path)

    if df.empty:
        return {
            "available": False,
            "total_windows": 0,
            "pause_rate": 0.0,
            "execute_rate": 0.0,
            "bad_rate_when_paused": 0.0,
            "bad_rate_when_executed": 0.0,
            "discrimination_gap": 0.0,
            "agent_accuracy": 0.0,
            "unnecessary_pause_rate": 0.0,
            "bad_window_recall": 0.0,
            "verdict": "not_available",
            "pause_bad": 0,
            "pause_good": 0,
            "execute_bad": 0,
            "execute_good": 0,
        }

    row = df.iloc[0]

    return {
        "available": True,
        "total_windows": _safe_int(row.get("total_windows")),
        "pause_rate": _safe_float(row.get("pause_rate")),
        "execute_rate": _safe_float(row.get("execute_rate")),
        "bad_rate_when_paused": _safe_float(row.get("bad_rate_when_paused")),
        "bad_rate_when_executed": _safe_float(row.get("bad_rate_when_executed")),
        "discrimination_gap": _safe_float(row.get("discrimination_gap")),
        "agent_accuracy": _safe_float(row.get("agent_accuracy")),
        "unnecessary_pause_rate": _safe_float(row.get("unnecessary_pause_rate")),
        "bad_window_recall": _safe_float(row.get("bad_window_recall")),
        "verdict": str(row.get("verdict", "unknown")),
        "pause_bad": _safe_int(row.get("pause_bad")),
        "pause_good": _safe_int(row.get("pause_good")),
        "execute_bad": _safe_int(row.get("execute_bad")),
        "execute_good": _safe_int(row.get("execute_good")),
    }


def load_episode_cards(data_dir: str | Path = "data") -> pd.DataFrame:
    data_dir = Path(data_dir)
    path = data_dir / "episode_avoided_cards.csv"

    df = _load_csv(path)

    if df.empty:
        return pd.DataFrame()

    numeric_cols = [
        "case_id",
        "start_block",
        "future_block",
        "horizon_blocks",
        "future_gas_dij",
        "future_execution_risk_score",
        "avoided_bad_exposure",
        "avoided_future_risk_exposure",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df


def build_product_proof(data_dir: str | Path = "data") -> dict[str, Any]:
    return {
        "counterfactual": build_counterfactual_summary(data_dir),
        "base_rate": build_base_rate_summary(data_dir),
        "episode_cards": load_episode_cards(data_dir),
    }


def format_percent(value: float) -> str:
    return _percent(value)


def format_float(value: float) -> str:
    return f"{value:.6f}"
