from __future__ import annotations

import math
import os
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


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    try:
        return bool(value)
    except Exception:
        return default


def _load_csv(path: str | Path, name: str) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"{name} not found: {path}")

    df = pd.read_csv(path)

    if df.empty:
        raise RuntimeError(f"{name} is empty: {path}")

    return df


def _normalize_bool_column(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([False] * len(df), index=df.index)

    return df[col].apply(_safe_bool)


def _prepare_examples(
    *,
    eval_df: pd.DataFrame,
    log_df: pd.DataFrame,
    horizon_blocks: int,
    top_n: int,
) -> pd.DataFrame:
    eval_df = eval_df.copy()
    log_df = log_df.copy()

    eval_df["horizon_blocks"] = pd.to_numeric(
        eval_df["horizon_blocks"],
        errors="coerce",
    ).fillna(0).astype(int)

    eval_df = eval_df[eval_df["horizon_blocks"] == horizon_blocks].copy()

    if eval_df.empty:
        raise RuntimeError(
            f"No counterfactual rows found for horizon_blocks={horizon_blocks}."
        )

    eval_df["agent_avoided_bad_execution_bool"] = _normalize_bool_column(
        eval_df,
        "agent_avoided_bad_execution",
    )

    eval_df["future_bad_execution_bool"] = _normalize_bool_column(
        eval_df,
        "future_bad_execution",
    )

    eval_df["start_agent_risk_state"] = eval_df["start_agent_risk_state"].astype(str)
    eval_df["start_agent_execution_mode"] = eval_df["start_agent_execution_mode"].astype(str)

    examples = eval_df[
        (eval_df["start_agent_risk_state"].str.upper() == "HIGH_STRESS")
        & (eval_df["start_agent_execution_mode"].str.upper() == "PAUSE")
        & (eval_df["agent_avoided_bad_execution_bool"])
    ].copy()

    if examples.empty:
        examples = eval_df[
            (eval_df["start_agent_execution_mode"].str.upper() == "PAUSE")
            & (eval_df["future_bad_execution_bool"])
        ].copy()

    if examples.empty:
        return pd.DataFrame()

    numeric_cols = [
        "start_block",
        "future_block",
        "future_composite_dij",
        "future_gas_dij",
        "future_base_fee_dij",
        "future_execution_risk_score",
        "baseline_bad_exposure",
        "agent_bad_exposure",
        "avoided_bad_exposure",
        "baseline_future_risk_exposure",
        "agent_future_risk_exposure",
        "avoided_future_risk_exposure",
    ]

    for col in numeric_cols:
        if col in examples.columns:
            examples[col] = pd.to_numeric(examples[col], errors="coerce").fillna(0.0)

    if "avoided_future_risk_exposure" in examples.columns:
        examples = examples.sort_values(
            "avoided_future_risk_exposure",
            ascending=False,
        )
    elif "avoided_bad_exposure" in examples.columns:
        examples = examples.sort_values(
            "avoided_bad_exposure",
            ascending=False,
        )

    log_df["latest_block"] = pd.to_numeric(
        log_df["latest_block"],
        errors="coerce",
    ).fillna(0).astype(int)

    log_cols = [
        "timestamp",
        "latest_block",
        "block_hash",
        "regime",
        "composite_dij",
        "tx_dij",
        "gas_dij",
        "base_fee_dij",
        "hysteresis_alert_active",
        "hysteresis_event",
        "episode_id",
        "agent_risk_state",
        "agent_execution_mode",
        "agent_notional",
        "baseline_notional",
        "avoided_notional",
        "execution_risk_score",
    ]

    existing_log_cols = [col for col in log_cols if col in log_df.columns]

    merged = examples.merge(
        log_df[existing_log_cols],
        left_on="start_block",
        right_on="latest_block",
        how="left",
        suffixes=("", "_start"),
    )

    rows = []

    for _, row in merged.head(top_n).iterrows():
        start_block = int(_safe_float(row.get("start_block")))
        future_block = int(_safe_float(row.get("future_block")))
        horizon = int(_safe_float(row.get("horizon_blocks")))

        future_risk = _safe_float(row.get("future_execution_risk_score"))
        future_gas = _safe_float(row.get("future_gas_dij"))
        future_base_fee = _safe_float(row.get("future_base_fee_dij"))
        future_composite = _safe_float(row.get("future_composite_dij"))

        avoided_bad = _safe_float(row.get("avoided_bad_exposure"))
        avoided_risk = _safe_float(row.get("avoided_future_risk_exposure"))

        start_gas = _safe_float(row.get("gas_dij"))
        start_base_fee = _safe_float(row.get("base_fee_dij"))
        start_composite = _safe_float(row.get("composite_dij"))
        start_risk = _safe_float(row.get("execution_risk_score"))

        timestamp = row.get("timestamp", "")

        commercial_read = (
            f"At block {start_block}, the agent classified the network as "
            f"{row.get('start_agent_risk_state')} and chose "
            f"{row.get('start_agent_execution_mode')}. "
            f"{horizon} blocks later, the future window was still risky "
            f"(future risk={future_risk:.4f}, gas d_ij={future_gas:.4f}). "
            f"The baseline would have executed into that window, while the agent avoided it."
        )

        rows.append(
            {
                "timestamp": timestamp,
                "start_block": start_block,
                "future_block": future_block,
                "horizon_blocks": horizon,
                "start_regime": row.get("start_regime", row.get("regime", "")),
                "start_agent_risk_state": row.get("start_agent_risk_state"),
                "start_agent_execution_mode": row.get("start_agent_execution_mode"),
                "start_composite_dij": start_composite,
                "start_gas_dij": start_gas,
                "start_base_fee_dij": start_base_fee,
                "start_execution_risk_score": start_risk,
                "future_composite_dij": future_composite,
                "future_gas_dij": future_gas,
                "future_base_fee_dij": future_base_fee,
                "future_execution_risk_score": future_risk,
                "baseline_notional": row.get("baseline_notional"),
                "agent_notional": row.get("agent_notional"),
                "baseline_bad_exposure": row.get("baseline_bad_exposure"),
                "agent_bad_exposure": row.get("agent_bad_exposure"),
                "avoided_bad_exposure": avoided_bad,
                "baseline_future_risk_exposure": row.get("baseline_future_risk_exposure"),
                "agent_future_risk_exposure": row.get("agent_future_risk_exposure"),
                "avoided_future_risk_exposure": avoided_risk,
                "commercial_read": commercial_read,
            }
        )

    return pd.DataFrame(rows)


def _write_markdown_report(
    *,
    examples_df: pd.DataFrame,
    output_path: str | Path,
    horizon_blocks: int,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    lines.append("# Example Avoided Execution Windows")
    lines.append("")
    lines.append("## Product Question")
    lines.append("")
    lines.append(
        "Can we show concrete examples where the agent paused and avoided "
        "a bad execution window that the baseline would have entered?"
    )
    lines.append("")

    if examples_df.empty:
        lines.append("No avoided examples found yet. Let the counterfactual logger run longer.")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    total_avoided_bad = examples_df["avoided_bad_exposure"].astype(float).sum()
    total_avoided_risk = examples_df["avoided_future_risk_exposure"].astype(float).sum()

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Horizon used: `{horizon_blocks}` blocks")
    lines.append(f"- Examples shown: `{len(examples_df)}`")
    lines.append(f"- Total avoided bad exposure in examples: `{total_avoided_bad:.6f}`")
    lines.append(f"- Total avoided future risk exposure in examples: `{total_avoided_risk:.6f}`")
    lines.append("")

    lines.append("## Quick User-Facing Examples")
    lines.append("")

    for i, row in examples_df.iterrows():
        lines.append(f"### Example {i + 1}")
        lines.append("")
        lines.append(f"- Start block: `{int(row['start_block'])}`")
        lines.append(f"- Future block: `{int(row['future_block'])}`")
        lines.append(f"- Agent state: `{row['start_agent_risk_state']}`")
        lines.append(f"- Agent action: `{row['start_agent_execution_mode']}`")
        lines.append(f"- Start gas d_ij: `{float(row['start_gas_dij']):.4f}`")
        lines.append(f"- Future gas d_ij: `{float(row['future_gas_dij']):.4f}`")
        lines.append(f"- Future execution risk: `{float(row['future_execution_risk_score']):.4f}`")
        lines.append(f"- Avoided bad exposure: `{float(row['avoided_bad_exposure']):.6f}`")
        lines.append(f"- Avoided future risk exposure: `{float(row['avoided_future_risk_exposure']):.6f}`")
        lines.append("")
        lines.append(f"**Plain-English read:** {row['commercial_read']}")
        lines.append("")

    lines.append("## Guardrail")
    lines.append("")
    lines.append(
        "These are counterfactual proxy examples, not live PnL. "
        "They show where the agent branch avoided a future bad execution window "
        "that the baseline branch would have entered. Real metrics like actual gas paid, "
        "slippage, fill price vs mid, and transaction success rate can be added later."
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def export_avoided_examples_from_env() -> None:
    eval_path = os.getenv("AVOIDED_EXAMPLES_EVAL_PATH", "data/counterfactual_eval.csv")
    log_path = os.getenv("AVOIDED_EXAMPLES_LOG_PATH", "data/counterfactual_log.csv")
    output_csv = os.getenv("AVOIDED_EXAMPLES_OUTPUT_CSV", "data/avoided_windows_examples.csv")
    output_md = os.getenv("AVOIDED_EXAMPLES_OUTPUT_MD", "data/avoided_windows_examples.md")
    top_n = int(os.getenv("AVOIDED_EXAMPLES_TOP_N", "10"))
    horizon_blocks = int(os.getenv("AVOIDED_EXAMPLES_HORIZON_BLOCKS", "10"))

    eval_df = _load_csv(eval_path, "counterfactual eval")
    log_df = _load_csv(log_path, "counterfactual log")

    examples_df = _prepare_examples(
        eval_df=eval_df,
        log_df=log_df,
        horizon_blocks=horizon_blocks,
        top_n=top_n,
    )

    output_csv_path = Path(output_csv)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    examples_df.to_csv(output_csv_path, index=False)

    _write_markdown_report(
        examples_df=examples_df,
        output_path=output_md,
        horizon_blocks=horizon_blocks,
    )

    print("=" * 80)
    print("Avoided window examples exported")
    print("=" * 80)
    print(f"Eval input: {eval_path}")
    print(f"Log input:  {log_path}")
    print(f"CSV:        {output_csv}")
    print(f"Report:     {output_md}")
    print(f"Examples:   {len(examples_df)}")
    print("=" * 80)
