from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def analyze_lead_time_from_env() -> None:
    input_path = Path(os.getenv("LEAD_TIME_INPUT_PATH", "data/counterfactual_log.csv"))
    output_path = Path(os.getenv("LEAD_TIME_OUTPUT_PATH", "data/lead_time_report.csv"))
    report_path = Path(os.getenv("LEAD_TIME_REPORT_PATH", "data/lead_time_report.md"))

    enter = float(os.getenv("ALERT_ENTER_THRESHOLD", "1.0"))
    exit_ = float(os.getenv("ALERT_EXIT_THRESHOLD", "0.85"))

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found.")

    df = pd.read_csv(input_path)

    if df.empty:
        raise RuntimeError("Counterfactual log is empty.")

    df["latest_block"] = pd.to_numeric(df["latest_block"], errors="coerce").fillna(0).astype(int)
    df["gas_dij"] = pd.to_numeric(df["gas_dij"], errors="coerce").fillna(0.0)
    df["base_fee_dij"] = pd.to_numeric(df["base_fee_dij"], errors="coerce").fillna(0.0)

    df = df.sort_values("latest_block").reset_index(drop=True)

    events = []

    gas_crosses = df[(df["gas_dij"] >= enter)].copy()

    for _, gas_row in gas_crosses.iterrows():
        start_block = int(gas_row["latest_block"])

        future_base = df[
            (df["latest_block"] >= start_block)
            & (df["base_fee_dij"] >= enter)
        ]

        if future_base.empty:
            continue

        base_row = future_base.iloc[0]
        base_block = int(base_row["latest_block"])

        future_exit = df[
            (df["latest_block"] >= base_block)
            & (df["gas_dij"] <= exit_)
            & (df["base_fee_dij"] <= exit_)
        ]

        exit_block = None
        if not future_exit.empty:
            exit_block = int(future_exit.iloc[0]["latest_block"])

        events.append(
            {
                "gas_cross_block": start_block,
                "base_fee_cross_block": base_block,
                "gas_lead_blocks": base_block - start_block,
                "exit_block": exit_block,
                "episode_duration_blocks": (exit_block - start_block) if exit_block else None,
                "gas_dij_at_cross": gas_row["gas_dij"],
                "base_fee_dij_at_gas_cross": gas_row["base_fee_dij"],
                "base_fee_dij_at_cross": base_row["base_fee_dij"],
            }
        )

    result = pd.DataFrame(events)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(output_path, index=False)

    lines = []
    lines.append("# SUPT Lead-Time Report")
    lines.append("")
    lines.append("## Question")
    lines.append("")
    lines.append("How many blocks does gas d_ij typically lead base-fee d_ij into stress?")
    lines.append("")

    if result.empty:
        lines.append("No completed gas→base-fee lead events found yet.")
    else:
        lines.append(f"- Events found: `{len(result)}`")
        lines.append(f"- Median gas lead blocks: `{result['gas_lead_blocks'].median():.2f}`")
        lines.append(f"- Mean gas lead blocks: `{result['gas_lead_blocks'].mean():.2f}`")
        lines.append(f"- Min gas lead blocks: `{result['gas_lead_blocks'].min()}`")
        lines.append(f"- Max gas lead blocks: `{result['gas_lead_blocks'].max()}`")
        lines.append("")
        lines.append("## Event Table")
        lines.append("")
        lines.append(result.head(50).to_markdown(index=False))

    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 80)
    print("Lead-time analysis complete")
    print("=" * 80)
    print(f"Events: {len(result)}")
    print(f"Output: {output_path}")
    print(f"Report: {report_path}")
    print("=" * 80)

