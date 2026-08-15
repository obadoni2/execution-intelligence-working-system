from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


METRICS = [
    "paper_gas_paid_proxy",
    "paper_slippage_proxy",
    "paper_failed_tx_cost_proxy",
    "paper_confirmation_delay_blocks_proxy",
    "paper_execution_cost_proxy",
    "opportunity_capture_proxy",
]


def _reduction(baseline: float, agent: float) -> float:
    if baseline <= 0:
        return 0.0
    return (baseline - agent) / baseline


def _load_log(path: str | Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run paper execution logger first.")

    df = pd.read_csv(path)

    if df.empty:
        raise RuntimeError("paper_execution_log.csv is empty.")

    for col in METRICS + ["notional", "latest_block", "execution_risk_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df


def _build_pairs(df: pd.DataFrame) -> pd.DataFrame:
    baseline = df[df["branch"] == "baseline"].copy()
    agent = df[df["branch"] == "agent"].copy()

    baseline = baseline.set_index("source_id")
    agent = agent.set_index("source_id")

    joined = baseline.join(
        agent,
        lsuffix="_baseline",
        rsuffix="_agent",
        how="inner",
    ).reset_index()

    rows = []

    for _, row in joined.iterrows():
        out = {
            "source_id": row["source_id"],
            "latest_block": row.get("latest_block_agent", row.get("latest_block_baseline")),
            "agent_risk_state": row.get("risk_state_agent"),
            "agent_execution_mode": row.get("execution_mode_agent"),
            "baseline_notional": row.get("notional_baseline"),
            "agent_notional": row.get("notional_agent"),
        }

        for metric in METRICS:
            b = float(row.get(f"{metric}_baseline", 0.0))
            a = float(row.get(f"{metric}_agent", 0.0))
            out[f"baseline_{metric}"] = b
            out[f"agent_{metric}"] = a
            out[f"avoided_{metric}"] = b - a
            out[f"{metric}_reduction"] = _reduction(b, a)

        rows.append(out)

    return pd.DataFrame(rows)


def _build_summary(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []

    groups = pairs.groupby(["agent_risk_state", "agent_execution_mode"])

    for (state, mode), group in groups:
        row = {
            "agent_risk_state": state,
            "agent_execution_mode": mode,
            "rows": len(group),
            "mean_agent_notional": group["agent_notional"].mean(),
        }

        for metric in METRICS:
            baseline_total = group[f"baseline_{metric}"].sum()
            agent_total = group[f"agent_{metric}"].sum()
            avoided_total = group[f"avoided_{metric}"].sum()

            row[f"baseline_{metric}"] = baseline_total
            row[f"agent_{metric}"] = agent_total
            row[f"avoided_{metric}"] = avoided_total
            row[f"{metric}_reduction"] = _reduction(baseline_total, agent_total)

        rows.append(row)

    out = pd.DataFrame(rows)

    if not out.empty:
        out = out.sort_values(
            "paper_execution_cost_proxy_reduction",
            ascending=False,
        )

    return out


def _write_report(
    *,
    pairs: pd.DataFrame,
    summary: pd.DataFrame,
    report_path: str | Path,
) -> None:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total_baseline_cost = pairs["baseline_paper_execution_cost_proxy"].sum()
    total_agent_cost = pairs["agent_paper_execution_cost_proxy"].sum()
    total_avoided_cost = pairs["avoided_paper_execution_cost_proxy"].sum()

    total_reduction = _reduction(total_baseline_cost, total_agent_cost)

    baseline_gas = pairs["baseline_paper_gas_paid_proxy"].sum()
    agent_gas = pairs["agent_paper_gas_paid_proxy"].sum()

    baseline_slip = pairs["baseline_paper_slippage_proxy"].sum()
    agent_slip = pairs["agent_paper_slippage_proxy"].sum()

    baseline_failed = pairs["baseline_paper_failed_tx_cost_proxy"].sum()
    agent_failed = pairs["agent_paper_failed_tx_cost_proxy"].sum()

    lines: list[str] = []

    lines.append("# SUPT Paper Execution Metrics Report")
    lines.append("")
    lines.append("## Product Question")
    lines.append("")
    lines.append(
        "Does the agent reduce practical execution-cost proxies compared with "
        "a baseline that always executes full notional?"
    )
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"- Paired paper decisions: `{len(pairs)}`")
    lines.append(f"- Total baseline execution-cost proxy: `{total_baseline_cost:.6f}`")
    lines.append(f"- Total agent execution-cost proxy: `{total_agent_cost:.6f}`")
    lines.append(f"- Total avoided execution-cost proxy: `{total_avoided_cost:.6f}`")
    lines.append(f"- Execution-cost proxy reduction: `{total_reduction * 100:.2f}%`")
    lines.append("")
    lines.append("## Cost Components")
    lines.append("")
    lines.append("| Component | Baseline | Agent | Reduction |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| Gas paid proxy | {baseline_gas:.6f} | {agent_gas:.6f} | {_reduction(baseline_gas, agent_gas) * 100:.2f}% |"
    )
    lines.append(
        f"| Slippage proxy | {baseline_slip:.6f} | {agent_slip:.6f} | {_reduction(baseline_slip, agent_slip) * 100:.2f}% |"
    )
    lines.append(
        f"| Failed tx cost proxy | {baseline_failed:.6f} | {agent_failed:.6f} | {_reduction(baseline_failed, agent_failed) * 100:.2f}% |"
    )
    lines.append("")
    lines.append("## Per-Action Summary")
    lines.append("")

    if summary.empty:
        lines.append("No per-action summary available.")
    else:
        lines.append(summary.to_markdown(index=False))

    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append(
        "This is paper execution using proxy metrics, not live PnL. "
        "No real trade is placed. The purpose is to test whether the agent’s actions "
        "reduce practical execution-cost proxies before moving to small live execution."
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def evaluate_paper_execution_from_env() -> None:
    input_path = os.getenv("PAPER_EXECUTION_OUTPUT_PATH", "data/paper_execution_log.csv")
    pairs_path = os.getenv("PAPER_EXECUTION_PAIRS_PATH", "data/paper_execution_pairs.csv")
    summary_path = os.getenv("PAPER_EXECUTION_SUMMARY_PATH", "data/paper_execution_summary.csv")
    report_path = os.getenv("PAPER_EXECUTION_REPORT_PATH", "data/paper_execution_report.md")

    df = _load_log(input_path)
    pairs = _build_pairs(df)
    summary = _build_summary(pairs)

    Path(pairs_path).parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(pairs_path, index=False)

    Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)

    _write_report(
        pairs=pairs,
        summary=summary,
        report_path=report_path,
    )

    total_baseline_cost = pairs["baseline_paper_execution_cost_proxy"].sum()
    total_agent_cost = pairs["agent_paper_execution_cost_proxy"].sum()

    print("=" * 80)
    print("Paper execution evaluation complete")
    print("=" * 80)
    print(f"Input:   {input_path}")
    print(f"Pairs:   {pairs_path}")
    print(f"Summary: {summary_path}")
    print(f"Report:  {report_path}")
    print(f"Pairs:   {len(pairs)}")
    print(f"Cost reduction: {_reduction(total_baseline_cost, total_agent_cost) * 100:.2f}%")
    print("=" * 80)
