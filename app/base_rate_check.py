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


def _load_eval(path: str | Path, horizon_blocks: int) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/evaluate_counterfactuals.py first."
        )

    df = pd.read_csv(path)

    if df.empty:
        raise RuntimeError("counterfactual_eval.csv is empty.")

    df["horizon_blocks"] = pd.to_numeric(
        df["horizon_blocks"],
        errors="coerce",
    ).fillna(0).astype(int)

    df = df[df["horizon_blocks"] == horizon_blocks].copy()

    if df.empty:
        raise RuntimeError(
            f"No rows found for horizon_blocks={horizon_blocks}. "
            "Check COUNTERFACTUAL_HORIZONS_BLOCKS and rerun evaluator."
        )

    text_cols = [
        "start_agent_risk_state",
        "start_agent_execution_mode",
        "start_regime",
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    bool_cols = [
        "future_bad_execution",
        "baseline_would_execute_bad",
        "agent_would_execute_bad",
        "agent_avoided_bad_execution",
    ]

    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(_safe_bool)
        else:
            df[col] = False

    numeric_cols = [
        "start_block",
        "future_block",
        "baseline_notional",
        "agent_notional",
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
        "start_episode_id",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "agent_notional" not in df.columns:
        df["agent_notional"] = 1.0

    df["agent_paused"] = (
        df["start_agent_execution_mode"].str.upper().eq("PAUSE")
        | (df["agent_notional"] <= 0)
    )

    df["agent_executed"] = ~df["agent_paused"]
    df["future_bad"] = df["future_bad_execution"].apply(_safe_bool)

    return df.reset_index(drop=True)


def build_base_rate_check(df: pd.DataFrame) -> pd.DataFrame:
    pause_bad = int((df["agent_paused"] & df["future_bad"]).sum())
    pause_good = int((df["agent_paused"] & ~df["future_bad"]).sum())
    execute_bad = int((df["agent_executed"] & df["future_bad"]).sum())
    execute_good = int((df["agent_executed"] & ~df["future_bad"]).sum())

    pause_total = pause_bad + pause_good
    execute_total = execute_bad + execute_good
    total = pause_total + execute_total

    pause_rate = pause_total / total if total else 0.0
    execute_rate = execute_total / total if total else 0.0

    bad_rate_when_paused = pause_bad / pause_total if pause_total else 0.0
    bad_rate_when_executed = execute_bad / execute_total if execute_total else 0.0

    discrimination_gap = bad_rate_when_paused - bad_rate_when_executed

    agent_accuracy = (pause_bad + execute_good) / total if total else 0.0

    pause_precision = pause_bad / pause_total if pause_total else 0.0
    bad_window_recall = pause_bad / (pause_bad + execute_bad) if (pause_bad + execute_bad) else 0.0
    unnecessary_pause_rate = pause_good / pause_total if pause_total else 0.0
    missed_bad_rate = execute_bad / execute_total if execute_total else 0.0

    if pause_rate >= 0.80 and execute_total < 5:
        verdict = "needs_more_execute_windows"
    elif discrimination_gap >= 0.30 and agent_accuracy >= 0.65:
        verdict = "strong_discrimination"
    elif discrimination_gap >= 0.15:
        verdict = "promising_discrimination"
    else:
        verdict = "weak_or_unclear_discrimination"

    return pd.DataFrame(
        [
            {
                "horizon_blocks": int(df["horizon_blocks"].iloc[0]),
                "total_windows": total,

                "pause_bad": pause_bad,
                "pause_good": pause_good,
                "execute_bad": execute_bad,
                "execute_good": execute_good,

                "pause_total": pause_total,
                "execute_total": execute_total,

                "pause_rate": pause_rate,
                "execute_rate": execute_rate,

                "bad_rate_when_paused": bad_rate_when_paused,
                "bad_rate_when_executed": bad_rate_when_executed,
                "discrimination_gap": discrimination_gap,

                "agent_accuracy": agent_accuracy,
                "pause_precision": pause_precision,
                "bad_window_recall": bad_window_recall,
                "unnecessary_pause_rate": unnecessary_pause_rate,
                "missed_bad_rate": missed_bad_rate,

                "verdict": verdict,
            }
        ]
    )


def _episode_key(row: pd.Series) -> str:
    if "start_episode_id" in row.index:
        episode = _safe_float(row.get("start_episode_id"))
        if episode > 0:
            return f"episode_{int(episode)}"

    future_block = int(_safe_float(row.get("future_block")))
    return f"future_block_{future_block}"


def build_episode_cards(df: pd.DataFrame, top_k: int) -> pd.DataFrame:
    examples = df[
        (df["start_agent_risk_state"].str.upper() == "HIGH_STRESS")
        & (df["start_agent_execution_mode"].str.upper() == "PAUSE")
        & (df["agent_avoided_bad_execution"].apply(_safe_bool))
    ].copy()

    if examples.empty:
        return pd.DataFrame()

    examples["episode_key"] = examples.apply(_episode_key, axis=1)

    examples = examples.sort_values(
        "avoided_future_risk_exposure",
        ascending=False,
    )

    # One representative row per episode/future window.
    deduped = (
        examples.groupby("episode_key", as_index=False)
        .head(1)
        .sort_values("avoided_future_risk_exposure", ascending=False)
        .head(top_k)
        .copy()
    )

    rows: list[dict[str, Any]] = []

    for idx, row in deduped.iterrows():
        case_id = len(rows) + 1

        start_block = int(_safe_float(row.get("start_block")))
        future_block = int(_safe_float(row.get("future_block")))
        horizon = int(_safe_float(row.get("horizon_blocks")))

        future_risk = _safe_float(row.get("future_execution_risk_score"))
        future_gas = _safe_float(row.get("future_gas_dij"))
        future_base_fee = _safe_float(row.get("future_base_fee_dij"))
        future_composite = _safe_float(row.get("future_composite_dij"))

        avoided_bad = _safe_float(row.get("avoided_bad_exposure"))
        avoided_risk = _safe_float(row.get("avoided_future_risk_exposure"))

        plain_english = (
            f"At block {start_block}, the agent classified Ethereum as HIGH_STRESS "
            f"and chose PAUSE. The baseline would have executed full notional. "
            f"{horizon} blocks later, the future window was still bad "
            f"(future risk={future_risk:.4f}, gas d_ij={future_gas:.4f}). "
            f"The agent avoided that bad execution window."
        )

        rows.append(
            {
                "case_id": case_id,
                "episode_key": row.get("episode_key"),
                "start_block": start_block,
                "future_block": future_block,
                "horizon_blocks": horizon,

                "agent_state": row.get("start_agent_risk_state"),
                "agent_action": row.get("start_agent_execution_mode"),
                "baseline_action": "EXECUTE_FULL",

                "future_composite_dij": future_composite,
                "future_gas_dij": future_gas,
                "future_base_fee_dij": future_base_fee,
                "future_execution_risk_score": future_risk,

                "avoided_bad_exposure": avoided_bad,
                "avoided_future_risk_exposure": avoided_risk,

                "plain_english": plain_english,
            }
        )

    return pd.DataFrame(rows)


def write_markdown_report(
    *,
    base_rate_df: pd.DataFrame,
    cards_df: pd.DataFrame,
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    lines.append("# Base-Rate Sanity Check + Episode Demo Cards")
    lines.append("")
    lines.append("## Why this matters")
    lines.append("")
    lines.append(
        "This checks whether the agent is truly discriminating risk, "
        "not just pausing so often that it catches bad windows by default."
    )
    lines.append("")

    if base_rate_df.empty:
        lines.append("No base-rate result available.")
    else:
        row = base_rate_df.iloc[0]

        lines.append("## 2×2 Truth Table")
        lines.append("")
        lines.append("| Agent decision | Future bad | Future good |")
        lines.append("|---|---:|---:|")
        lines.append(
            f"| PAUSE | {int(row['pause_bad'])} | {int(row['pause_good'])} |"
        )
        lines.append(
            f"| EXECUTE / REDUCE / RESUME | {int(row['execute_bad'])} | {int(row['execute_good'])} |"
        )
        lines.append("")
        lines.append("## Metrics")
        lines.append("")
        lines.append(f"- Total windows: `{int(row['total_windows'])}`")
        lines.append(f"- Pause rate: `{float(row['pause_rate']) * 100:.2f}%`")
        lines.append(f"- Execute rate: `{float(row['execute_rate']) * 100:.2f}%`")
        lines.append(f"- Bad rate when paused: `{float(row['bad_rate_when_paused']) * 100:.2f}%`")
        lines.append(f"- Bad rate when executed: `{float(row['bad_rate_when_executed']) * 100:.2f}%`")
        lines.append(f"- Discrimination gap: `{float(row['discrimination_gap']) * 100:.2f}%`")
        lines.append(f"- Agent binary accuracy: `{float(row['agent_accuracy']) * 100:.2f}%`")
        lines.append(f"- Bad-window recall: `{float(row['bad_window_recall']) * 100:.2f}%`")
        lines.append(f"- Unnecessary pause rate: `{float(row['unnecessary_pause_rate']) * 100:.2f}%`")
        lines.append(f"- Verdict: `{row['verdict']}`")
        lines.append("")

    lines.append("## Episode-Level Demo Cards")
    lines.append("")

    if cards_df.empty:
        lines.append("No episode-level avoided cards found yet.")
    else:
        for _, card in cards_df.iterrows():
            lines.append(f"### Case {int(card['case_id'])}: HIGH_STRESS → PAUSE")
            lines.append("")
            lines.append(f"- Episode key: `{card['episode_key']}`")
            lines.append(f"- Start block: `{int(card['start_block'])}`")
            lines.append(f"- Future block: `{int(card['future_block'])}`")
            lines.append(f"- Horizon: `{int(card['horizon_blocks'])}` blocks")
            lines.append(f"- Agent action: `{card['agent_action']}`")
            lines.append(f"- Baseline action: `{card['baseline_action']}`")
            lines.append(f"- Future gas d_ij: `{float(card['future_gas_dij']):.4f}`")
            lines.append(f"- Future execution risk: `{float(card['future_execution_risk_score']):.4f}`")
            lines.append(f"- Avoided bad exposure: `{float(card['avoided_bad_exposure']):.6f}`")
            lines.append(f"- Avoided future risk exposure: `{float(card['avoided_future_risk_exposure']):.6f}`")
            lines.append("")
            lines.append(f"**Plain-English read:** {card['plain_english']}")
            lines.append("")

    lines.append("## Guardrail")
    lines.append("")
    lines.append(
        "This is still proxy-based counterfactual evaluation, not live PnL. "
        "The purpose is to verify whether the agent makes useful time-varying "
        "decisions before showing avoided-window examples externally."
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_base_rate_check_from_env() -> None:
    eval_path = os.getenv("BASE_RATE_INPUT_EVAL_PATH", "data/counterfactual_eval.csv")
    base_csv = os.getenv("BASE_RATE_OUTPUT_CSV", "data/base_rate_check.csv")
    base_md = os.getenv("BASE_RATE_OUTPUT_MD", "data/base_rate_check.md")
    cards_csv = os.getenv("BASE_RATE_EPISODE_CARDS_CSV", "data/episode_avoided_cards.csv")
    cards_md = os.getenv("BASE_RATE_EPISODE_CARDS_MD", "data/episode_avoided_cards.md")

    horizon_blocks = int(os.getenv("BASE_RATE_HORIZON_BLOCKS", "10"))
    top_k = int(os.getenv("BASE_RATE_TOP_K_EPISODES", "3"))

    df = _load_eval(eval_path, horizon_blocks=horizon_blocks)

    base_rate_df = build_base_rate_check(df)
    cards_df = build_episode_cards(df, top_k=top_k)

    Path(base_csv).parent.mkdir(parents=True, exist_ok=True)
    base_rate_df.to_csv(base_csv, index=False)

    Path(cards_csv).parent.mkdir(parents=True, exist_ok=True)
    cards_df.to_csv(cards_csv, index=False)

    write_markdown_report(
        base_rate_df=base_rate_df,
        cards_df=cards_df,
        output_path=base_md,
    )

    write_markdown_report(
        base_rate_df=base_rate_df,
        cards_df=cards_df,
        output_path=cards_md,
    )

    row = base_rate_df.iloc[0]

    print("=" * 80)
    print("Base-rate sanity check complete")
    print("=" * 80)
    print(f"Input:              {eval_path}")
    print(f"Base-rate CSV:      {base_csv}")
    print(f"Base-rate report:   {base_md}")
    print(f"Episode cards CSV:  {cards_csv}")
    print(f"Episode cards MD:   {cards_md}")
    print("-" * 80)
    print(f"Total windows:      {int(row['total_windows'])}")
    print(f"Pause rate:         {float(row['pause_rate']) * 100:.2f}%")
    print(f"Bad when paused:    {float(row['bad_rate_when_paused']) * 100:.2f}%")
    print(f"Bad when executed:  {float(row['bad_rate_when_executed']) * 100:.2f}%")
    print(f"Gap:                {float(row['discrimination_gap']) * 100:.2f}%")
    print(f"Accuracy:           {float(row['agent_accuracy']) * 100:.2f}%")
    print(f"Verdict:            {row['verdict']}")
    print(f"Episode cards:      {len(cards_df)}")
    print("=" * 80)
