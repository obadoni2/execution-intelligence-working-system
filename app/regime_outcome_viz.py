from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def build_regime_outcome_plots_from_env() -> None:
    input_path = Path(os.getenv("COUNTERFACTUAL_EVAL_PATH", "data/counterfactual_eval.csv"))
    output_dir = Path(os.getenv("OUTCOME_FIGURES_DIR", "reports/figures"))

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} not found. Run evaluate_counterfactuals.py first.")

    df = pd.read_csv(input_path)

    if df.empty:
        raise RuntimeError("Counterfactual eval file is empty.")

    output_dir.mkdir(parents=True, exist_ok=True)

    numeric_cols = [
        "future_composite_dij",
        "future_gas_dij",
        "future_base_fee_dij",
        "future_execution_risk_score",
        "avoided_future_risk_exposure",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Scatter: future gas stress vs future risk score
    plt.figure(figsize=(10, 6))
    plt.scatter(df["future_gas_dij"], df["future_execution_risk_score"], alpha=0.7)
    plt.xlabel("Future gas d_ij")
    plt.ylabel("Future execution risk score")
    plt.title("Gas d_ij vs Future Execution Risk")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "gas_dij_vs_future_risk.png", dpi=160)
    plt.close()

    # Boxplot: future risk by starting agent state
    states = sorted(df["start_agent_risk_state"].dropna().unique().tolist())
    data = [
        df[df["start_agent_risk_state"] == state]["future_execution_risk_score"].values
        for state in states
    ]

    if states:
        plt.figure(figsize=(10, 6))
        plt.boxplot(data, labels=states)
        plt.xlabel("Starting agent risk state")
        plt.ylabel("Future execution risk score")
        plt.title("Future Risk Distribution by Agent State")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "future_risk_by_agent_state.png", dpi=160)
        plt.close()

    # Bar: average avoided future risk by state
    grouped = (
        df.groupby("start_agent_risk_state")["avoided_future_risk_exposure"]
        .mean()
        .sort_values(ascending=False)
    )

    if not grouped.empty:
        plt.figure(figsize=(10, 6))
        grouped.plot(kind="bar")
        plt.xlabel("Starting agent risk state")
        plt.ylabel("Mean avoided future risk exposure")
        plt.title("Mean Avoided Future Risk by Agent State")
        plt.grid(True, axis="y", alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "avoided_risk_by_agent_state.png", dpi=160)
        plt.close()

    print("=" * 80)
    print("Regime outcome plots written")
    print("=" * 80)
    print(f"Output dir: {output_dir}")
    print("=" * 80)
