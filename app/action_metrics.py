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

    return bool(value)


def _load_eval(path: str | Path, horizon_blocks: int) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run evaluate_counterfactuals.py first.")

    df = pd.read_csv(path)

    if df.empty:
        raise RuntimeError("counterfactual_eval.csv is empty.")

    df["horizon_blocks"] = pd.to_numeric(
        df["horizon_blocks"],
        errors="coerce",
    ).fillna(0).astype(int)

    df = df[df["horizon_blocks"] == horizon_blocks].copy()

    if df.empty:
        raise RuntimeError(f"No rows found for horizon_blocks={horizon_blocks}")

    bool_cols = [
        "future_bad_execution",
        "agent_avoided_bad_execution",
    ]

    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(_safe_bool)
        else:
            df[col] = False

    numeric_cols = [
        "baseline_bad_exposure",
        "agent_bad_exposure",
        "avoided_bad_exposure",
        "baseline_future_risk_exposure",
        "agent_future_risk_exposure",
        "avoided_future_risk_exposure",
        "future_execution_risk_score",
        "future_gas_dij",
        "future_base_fee_dij",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    df["start_agent_risk_state"] = df["start_agent_risk_state"].fillna("").astype(str)
    df["start_agent_execution_mode"] = df["start_agent_execution_mode"].fillna("").astype(str)

    return df


def _reduction(avoided: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0
    return avoided / baseline


def build_action_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    grouped = df.groupby(["start_agent_risk_state", "start_agent_execution_mode"])

    for (state, mode), group in grouped:
        rows_count = len(group)

        baseline_bad = float(group["baseline_bad_exposure"].sum())
        agent_bad = float(group["agent_bad_exposure"].sum())
        avoided_bad = float(group["avoided_bad_exposure"].sum())

        baseline_risk = float(group["baseline_future_risk_exposure"].sum())
        agent_risk = float(group["agent_future_risk_exposure"].sum())
        avoided_risk = float(group["avoided_future_risk_exposure"].sum())

        future_bad_rate = float(group["future_bad_execution"].astype(bool).mean())
        avoided_bad_count = int(group["agent_avoided_bad_execution"].astype(bool).sum())

        rows.append(
            {
                "risk_state": state,
                "execution_mode": mode,
                "rows": rows_count,

                "future_bad_rate": future_bad_rate,
                "avoided_bad_count": avoided_bad_count,

                "baseline_bad_exposure": baseline_bad,
                "agent_bad_exposure": agent_bad,
                "avoided_bad_exposure": avoided_bad,
                "bad_exposure_reduction": _reduction(avoided_bad, baseline_bad),

                "baseline_future_risk_exposure": baseline_risk,
                "agent_future_risk_exposure": agent_risk,
                "avoided_future_risk_exposure": avoided_risk,
                "future_risk_reduction": _reduction(avoided_risk, baseline_risk),

                "mean_future_risk_score": float(group["future_execution_risk_score"].mean()),
                "mean_future_gas_dij": float(group["future_gas_dij"].mean()),
                "mean_future_base_fee_dij": float(group["future_base_fee_dij"].mean()),
            }
        )

    out = pd.DataFrame(rows)

    if not out.empty:
        out = out.sort_values(
            ["bad_exposure_reduction", "future_risk_reduction", "rows"],
            ascending=[False, False, False],
        )

    return out


def write_action_metrics_report(
    *,
    metrics_df: pd.DataFrame,
    output_path: str | Path,
    horizon_blocks: int,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    lines.append("# Gradient Execution Per-Action Metrics")
    lines.append("")
    lines.append("## Product Question")
    lines.append("")
    lines.append(
        "Which agent actions are actually improving future execution-risk outcomes "
        "against the baseline?"
    )
    lines.append("")
    lines.append(f"- Horizon: `{horizon_blocks}` blocks")
    lines.append("")

    if metrics_df.empty:
        lines.append("No action metrics available yet.")
    else:
        lines.append("## Per-Action Summary")
        lines.append("")
        lines.append(metrics_df.to_markdown(index=False))

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "HIGH_STRESS / PAUSE should show high future bad-rate and high avoided exposure. "
        "EARLY_CAUTION and CAUTION should show whether reducing size before full stress "
        "improves outcomes. RECOVERY should show whether gradual resume is safe. "
        "NORMAL should ideally have low future bad-rate."
    )
    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append(
        "This is still proxy-based counterfactual evaluation, not live PnL. "
        "Real execution metrics can later be added: gas paid, slippage, fill price vs mid, "
        "confirmation delay, and transaction success rate."
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_action_metrics_from_env() -> None:
    input_path = os.getenv("ACTION_METRICS_INPUT_PATH", "data/counterfactual_eval.csv")
    output_csv = os.getenv("ACTION_METRICS_OUTPUT_CSV", "data/action_metrics.csv")
    output_md = os.getenv("ACTION_METRICS_OUTPUT_MD", "data/action_metrics.md")
    horizon_blocks = int(os.getenv("ACTION_METRICS_HORIZON_BLOCKS", "10"))

    df = _load_eval(input_path, horizon_blocks=horizon_blocks)
    metrics = build_action_metrics(df)

    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_csv, index=False)

    write_action_metrics_report(
        metrics_df=metrics,
        output_path=output_md,
        horizon_blocks=horizon_blocks,
    )

    print("=" * 80)
    print("Gradient action metrics complete")
    print("=" * 80)
    print(f"Input:   {input_path}")
    print(f"CSV:     {output_csv}")
    print(f"Report:  {output_md}")
    print(f"Horizon: {horizon_blocks}")
    print(f"Rows:    {len(metrics)}")
    print("=" * 80)
