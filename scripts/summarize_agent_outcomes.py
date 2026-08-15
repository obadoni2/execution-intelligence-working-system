from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    path = Path("data/agent_decisions.csv")

    if not path.exists():
        raise FileNotFoundError("data/agent_decisions.csv not found. Run the agent first.")

    df = pd.read_csv(path)

    if df.empty:
        raise RuntimeError("Agent decision log is empty.")

    numeric_cols = [
        "baseline_notional",
        "agent_notional",
        "avoided_notional",
        "execution_risk_score",
        "baseline_risk_exposure",
        "agent_risk_exposure",
        "avoided_risk_exposure",
        "gas_risk_proxy",
        "slippage_risk_proxy",
        "confirmation_risk_proxy",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    total_baseline_exposure = df["baseline_risk_exposure"].sum()
    total_agent_exposure = df["agent_risk_exposure"].sum()
    total_avoided_exposure = df["avoided_risk_exposure"].sum()

    exposure_reduction = 0.0
    if total_baseline_exposure > 0:
        exposure_reduction = total_avoided_exposure / total_baseline_exposure

    state_counts = df["risk_state"].value_counts().to_dict()
    mode_counts = df["execution_mode"].value_counts().to_dict()

    print("=" * 80)
    print("SUPT Ethereum Regime Agent Outcome Summary")
    print("=" * 80)
    print(f"Rows logged: {len(df)}")
    print(f"Risk states: {state_counts}")
    print(f"Execution modes: {mode_counts}")
    print("-" * 80)
    print(f"Total baseline risk exposure: {total_baseline_exposure:.6f}")
    print(f"Total agent risk exposure:    {total_agent_exposure:.6f}")
    print(f"Total avoided risk exposure:  {total_avoided_exposure:.6f}")
    print(f"Exposure reduction proxy:     {exposure_reduction * 100:.2f}%")
    print("-" * 80)
    print(f"Mean execution risk score:    {df['execution_risk_score'].mean():.6f}")
    print(f"Mean gas risk proxy:          {df['gas_risk_proxy'].mean():.6f}")
    print(f"Mean slippage risk proxy:     {df['slippage_risk_proxy'].mean():.6f}")
    print(f"Mean confirmation risk proxy: {df['confirmation_risk_proxy'].mean():.6f}")
    print("=" * 80)

    out_path = Path("data/agent_outcome_summary.csv")
    summary = pd.DataFrame(
        [
            {
                "rows_logged": len(df),
                "total_baseline_risk_exposure": total_baseline_exposure,
                "total_agent_risk_exposure": total_agent_exposure,
                "total_avoided_risk_exposure": total_avoided_exposure,
                "exposure_reduction_proxy": exposure_reduction,
                "mean_execution_risk_score": df["execution_risk_score"].mean(),
                "mean_gas_risk_proxy": df["gas_risk_proxy"].mean(),
                "mean_slippage_risk_proxy": df["slippage_risk_proxy"].mean(),
                "mean_confirmation_risk_proxy": df["confirmation_risk_proxy"].mean(),
            }
        ]
    )

    summary.to_csv(out_path, index=False)
    print(f"Summary written to: {out_path}")


if __name__ == "__main__":
    main()
