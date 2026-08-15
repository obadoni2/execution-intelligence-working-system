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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    return _safe_float(os.getenv(name), default)


def _env_int(name: str, default: int) -> int:
    return _safe_int(os.getenv(name), default)


def _load_log(path: str | Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Let the counterfactual logger run first.")

    df = pd.read_csv(path)

    if df.empty:
        raise RuntimeError("counterfactual_log.csv is empty.")

    numeric_cols = [
        "latest_block",
        "composite_dij",
        "tx_dij",
        "gas_dij",
        "base_fee_dij",
        "agent_notional",
        "baseline_notional",
        "execution_risk_score",
        "gas_pressure_proxy",
        "slippage_pressure_proxy",
        "failed_tx_risk_proxy",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    text_cols = [
        "timestamp",
        "chain",
        "regime",
        "agent_risk_state",
        "agent_execution_mode",
        "agent_action",
    ]

    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
        else:
            df[col] = ""

    df = df[df["latest_block"] > 0].copy()
    df["latest_block"] = df["latest_block"].astype(int)
    df = df.sort_values("latest_block").drop_duplicates("latest_block").reset_index(drop=True)

    return df


def _execution_cost(
    *,
    notional: float,
    execution_risk_score: float,
    gas_pressure_proxy: float,
    slippage_pressure_proxy: float,
    failed_tx_risk_proxy: float,
) -> float:
    if notional <= 0:
        return 0.0

    gas_weight = _env_float("TRANSITION_GAS_COST_WEIGHT", 1.0)
    slip_weight = _env_float("TRANSITION_SLIPPAGE_WEIGHT", 1.0)
    fail_weight = _env_float("TRANSITION_FAILED_TX_WEIGHT", 1.0)
    delay_weight = _env_float("TRANSITION_CONFIRMATION_DELAY_WEIGHT", 0.10)

    gas_cost = notional * gas_pressure_proxy * gas_weight

    slippage_pressure = max(0.0, slippage_pressure_proxy - 0.75)
    slippage_cost = notional * slippage_pressure * slip_weight

    failed_cost = notional * failed_tx_risk_proxy * fail_weight

    confirmation_delay_blocks = max(
        1.0,
        1.0 + (execution_risk_score * 2.0) + (gas_pressure_proxy * 2.0),
    )
    delay_cost = notional * confirmation_delay_blocks * delay_weight

    return gas_cost + slippage_cost + failed_cost + delay_cost


def _add_policy_costs(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    composite_threshold = _env_float("TRANSITION_COMPOSITE_THRESHOLD", 1.0)
    reactive_pause_threshold = _env_float("TRANSITION_REACTIVE_PAUSE_AT_COMPOSITE", 1.0)

    gas_caution = _env_float("TRANSITION_GAS_BASELINE_CAUTION_THRESHOLD", 0.90)
    gas_stress = _env_float("TRANSITION_GAS_BASELINE_STRESS_THRESHOLD", 1.0)
    gas_caution_mult = _env_float("TRANSITION_GAS_BASELINE_CAUTION_MULTIPLIER", 0.35)

    out["always_notional"] = 1.0
    out["supt_notional"] = out["agent_notional"].fillna(1.0)

    out["reactive_notional"] = out["composite_dij"].apply(
        lambda x: 0.0 if x >= reactive_pause_threshold else 1.0
    )

    def gas_baseline_notional(gas: float) -> float:
        if gas >= gas_stress:
            return 0.0
        if gas >= gas_caution:
            return gas_caution_mult
        return 1.0

    out["gas_threshold_notional"] = out["gas_dij"].apply(gas_baseline_notional)

    for policy in ["always", "supt", "reactive", "gas_threshold"]:
        out[f"{policy}_cost"] = out.apply(
            lambda r: _execution_cost(
                notional=_safe_float(r.get(f"{policy}_notional")),
                execution_risk_score=_safe_float(r.get("execution_risk_score")),
                gas_pressure_proxy=_safe_float(r.get("gas_pressure_proxy")),
                slippage_pressure_proxy=_safe_float(r.get("slippage_pressure_proxy")),
                failed_tx_risk_proxy=_safe_float(r.get("failed_tx_risk_proxy")),
            ),
            axis=1,
        )

    out["is_clutch"] = out["composite_dij"] >= composite_threshold

    return out


def _find_clutch_crossings(df: pd.DataFrame) -> pd.DataFrame:
    composite_threshold = _env_float("TRANSITION_COMPOSITE_THRESHOLD", 1.0)

    rows = []
    prev_is_clutch = False

    for _, row in df.iterrows():
        is_clutch = _safe_float(row["composite_dij"]) >= composite_threshold

        if is_clutch and not prev_is_clutch:
            rows.append(row.to_dict())

        prev_is_clutch = is_clutch

    return pd.DataFrame(rows)


def _summarize_transition_event(
    *,
    event_id: int,
    event_row: pd.Series,
    df: pd.DataFrame,
) -> dict[str, Any]:
    pre_blocks = _env_int("TRANSITION_PRE_BLOCKS", 20)
    post_blocks = _env_int("TRANSITION_POST_BLOCKS", 20)

    gas_early = _env_float("TRANSITION_GAS_EARLY_THRESHOLD", 0.90)
    gas_stress = _env_float("TRANSITION_GAS_STRESS_THRESHOLD", 1.0)
    base_fee_early = _env_float("TRANSITION_BASE_FEE_EARLY_THRESHOLD", 0.85)

    clutch_block = int(event_row["latest_block"])

    pre = df[
        (df["latest_block"] >= clutch_block - pre_blocks)
        & (df["latest_block"] < clutch_block)
    ].copy()

    at = df[df["latest_block"] == clutch_block].copy()

    post = df[
        (df["latest_block"] > clutch_block)
        & (df["latest_block"] <= clutch_block + post_blocks)
    ].copy()

    full_window = df[
        (df["latest_block"] >= clutch_block - pre_blocks)
        & (df["latest_block"] <= clutch_block + post_blocks)
    ].copy()

    pre_divergence = pre[
        (
            (pre["gas_dij"] >= gas_early)
            | (pre["base_fee_dij"] >= base_fee_early)
        )
        & (pre["composite_dij"] < 1.0)
    ].copy()

    first_divergence_block = None
    lead_blocks = None

    if not pre_divergence.empty:
        first_divergence_block = int(pre_divergence.iloc[0]["latest_block"])
        lead_blocks = clutch_block - first_divergence_block

    pre_agent_caution = pre[
        pre["agent_risk_state"].str.upper().isin(
            ["EARLY_CAUTION", "CAUTION", "HIGH_STRESS"]
        )
    ].copy()

    first_agent_shift_block = None
    agent_lead_blocks = None

    if not pre_agent_caution.empty:
        first_agent_shift_block = int(pre_agent_caution.iloc[0]["latest_block"])
        agent_lead_blocks = clutch_block - first_agent_shift_block

    at_state = ""
    at_mode = ""

    if not at.empty:
        at_state = str(at.iloc[0].get("agent_risk_state", ""))
        at_mode = str(at.iloc[0].get("agent_execution_mode", ""))

    future_bad = False
    if not post.empty:
        future_bad = bool(
            (post["composite_dij"] >= 1.0).any()
            or (post["gas_dij"] >= gas_stress).any()
            or (post["execution_risk_score"] >= 1.0).any()
        )

    def total_cost(policy: str, frame: pd.DataFrame) -> float:
        if frame.empty:
            return 0.0
        return float(frame[f"{policy}_cost"].sum())

    always_cost = total_cost("always", full_window)
    supt_cost = total_cost("supt", full_window)
    reactive_cost = total_cost("reactive", full_window)
    gas_threshold_cost = total_cost("gas_threshold", full_window)

    def reduction_vs(baseline: float, agent: float) -> float:
        if baseline <= 0:
            return 0.0
        return (baseline - agent) / baseline

    return {
        "event_id": event_id,
        "clutch_block": clutch_block,
        "event_timestamp": event_row.get("timestamp", ""),
        "pre_window_blocks": pre_blocks,
        "post_window_blocks": post_blocks,

        "pre_rows": len(pre),
        "post_rows": len(post),
        "window_rows": len(full_window),

        "first_divergence_block": first_divergence_block,
        "gas_channel_lead_blocks": lead_blocks,
        "first_agent_shift_block": first_agent_shift_block,
        "agent_lead_blocks": agent_lead_blocks,

        "had_pre_divergence": first_divergence_block is not None,
        "had_pre_agent_shift": first_agent_shift_block is not None,

        "at_clutch_agent_state": at_state,
        "at_clutch_agent_mode": at_mode,

        "future_bad_after_clutch": future_bad,

        "always_cost": always_cost,
        "supt_cost": supt_cost,
        "reactive_cost": reactive_cost,
        "gas_threshold_cost": gas_threshold_cost,

        "supt_reduction_vs_always": reduction_vs(always_cost, supt_cost),
        "supt_reduction_vs_reactive": reduction_vs(reactive_cost, supt_cost),
        "supt_reduction_vs_gas_threshold": reduction_vs(gas_threshold_cost, supt_cost),

        "reactive_reduction_vs_always": reduction_vs(always_cost, reactive_cost),
        "gas_threshold_reduction_vs_always": reduction_vs(always_cost, gas_threshold_cost),
    }


def _build_failure_modes(df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    lookahead = _env_int("TRANSITION_LOOKAHEAD_BLOCKS", 20)

    rows = []

    early_rows = df[
        df["agent_risk_state"].str.upper().isin(["EARLY_CAUTION", "CAUTION"])
    ].copy()

    for _, row in early_rows.iterrows():
        block = int(row["latest_block"])
        future = df[
            (df["latest_block"] > block)
            & (df["latest_block"] <= block + lookahead)
        ]

        if future.empty:
            continue

        has_future_clutch = bool((future["composite_dij"] >= 1.0).any())

        if not has_future_clutch:
            rows.append(
                {
                    "failure_type": "early_caution_without_clutch",
                    "block": block,
                    "agent_state": row.get("agent_risk_state"),
                    "agent_mode": row.get("agent_execution_mode"),
                    "composite_dij": row.get("composite_dij"),
                    "gas_dij": row.get("gas_dij"),
                    "base_fee_dij": row.get("base_fee_dij"),
                    "lookahead_blocks": lookahead,
                    "note": "Agent shifted cautious but CLUTCH did not materialize within lookahead.",
                }
            )

    for _, event in events.iterrows():
        clutch_block = int(event["clutch_block"])

        if not bool(event["had_pre_divergence"]):
            rows.append(
                {
                    "failure_type": "clutch_without_prior_divergence",
                    "block": clutch_block,
                    "agent_state": event.get("at_clutch_agent_state"),
                    "agent_mode": event.get("at_clutch_agent_mode"),
                    "composite_dij": "",
                    "gas_dij": "",
                    "base_fee_dij": "",
                    "lookahead_blocks": lookahead,
                    "note": "CLUTCH occurred without prior gas/base-fee divergence in the pre-window.",
                }
            )

        if not bool(event["had_pre_agent_shift"]):
            rows.append(
                {
                    "failure_type": "clutch_without_prior_agent_shift",
                    "block": clutch_block,
                    "agent_state": event.get("at_clutch_agent_state"),
                    "agent_mode": event.get("at_clutch_agent_mode"),
                    "composite_dij": "",
                    "gas_dij": "",
                    "base_fee_dij": "",
                    "lookahead_blocks": lookahead,
                    "note": "CLUTCH occurred without prior EARLY_CAUTION/CAUTION/HIGH_STRESS action in the pre-window.",
                }
            )

    return pd.DataFrame(rows)


def _build_summary(events: pd.DataFrame, df: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    first_block = int(df["latest_block"].min())
    last_block = int(df["latest_block"].max())
    block_span = last_block - first_block
    approx_hours = block_span * 12 / 3600

    if events.empty:
        return pd.DataFrame(
            [
                {
                    "transitions": 0,
                    "first_block": first_block,
                    "last_block": last_block,
                    "block_span": block_span,
                    "approx_hours_at_12s_blocks": approx_hours,
                }
            ]
        )

    lead_series = pd.to_numeric(events["gas_channel_lead_blocks"], errors="coerce").dropna()
    agent_lead_series = pd.to_numeric(events["agent_lead_blocks"], errors="coerce").dropna()

    total_always = events["always_cost"].sum()
    total_supt = events["supt_cost"].sum()
    total_reactive = events["reactive_cost"].sum()
    total_gas = events["gas_threshold_cost"].sum()

    def reduction(baseline: float, agent: float) -> float:
        if baseline <= 0:
            return 0.0
        return (baseline - agent) / baseline

    false_early = 0
    missed_div = 0
    missed_agent = 0

    if not failures.empty:
        false_early = int((failures["failure_type"] == "early_caution_without_clutch").sum())
        missed_div = int((failures["failure_type"] == "clutch_without_prior_divergence").sum())
        missed_agent = int((failures["failure_type"] == "clutch_without_prior_agent_shift").sum())

    return pd.DataFrame(
        [
            {
                "transitions": len(events),
                "first_block": first_block,
                "last_block": last_block,
                "block_span": block_span,
                "approx_hours_at_12s_blocks": approx_hours,

                "pre_divergence_rate": float(events["had_pre_divergence"].mean()),
                "pre_agent_shift_rate": float(events["had_pre_agent_shift"].mean()),

                "median_gas_lead_blocks": float(lead_series.median()) if not lead_series.empty else 0.0,
                "mean_gas_lead_blocks": float(lead_series.mean()) if not lead_series.empty else 0.0,
                "p10_gas_lead_blocks": float(lead_series.quantile(0.10)) if not lead_series.empty else 0.0,
                "p90_gas_lead_blocks": float(lead_series.quantile(0.90)) if not lead_series.empty else 0.0,

                "median_agent_lead_blocks": float(agent_lead_series.median()) if not agent_lead_series.empty else 0.0,
                "mean_agent_lead_blocks": float(agent_lead_series.mean()) if not agent_lead_series.empty else 0.0,

                "total_always_cost": total_always,
                "total_supt_cost": total_supt,
                "total_reactive_cost": total_reactive,
                "total_gas_threshold_cost": total_gas,

                "supt_reduction_vs_always": reduction(total_always, total_supt),
                "supt_reduction_vs_reactive": reduction(total_reactive, total_supt),
                "supt_reduction_vs_gas_threshold": reduction(total_gas, total_supt),

                "false_early_caution_count": false_early,
                "clutch_without_prior_divergence_count": missed_div,
                "clutch_without_prior_agent_shift_count": missed_agent,
            }
        ]
    )


def _write_report(
    *,
    events: pd.DataFrame,
    summary: pd.DataFrame,
    failures: pd.DataFrame,
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    row = summary.iloc[0]

    lines: list[str] = []

    lines.append("# SUPT Transition-Specific Validation Report")
    lines.append("")
    lines.append("## Product Question")
    lines.append("")
    lines.append(
        "Does the agent improve execution before CLUTCH becomes obvious, "
        "or is it only reacting after composite d_ij crosses 1.0?"
    )
    lines.append("")
    lines.append("## Validation Window")
    lines.append("")
    lines.append(f"- First block: `{int(row['first_block'])}`")
    lines.append(f"- Last block: `{int(row['last_block'])}`")
    lines.append(f"- Block span: `{int(row['block_span'])}`")
    lines.append(f"- Approx hours at 12s/block: `{float(row['approx_hours_at_12s_blocks']):.2f}`")
    lines.append(f"- CLUTCH transitions found: `{int(row['transitions'])}`")
    lines.append("")

    if int(row["transitions"]) > 0:
        lines.append("## Lead-Time Result")
        lines.append("")
        lines.append(f"- Pre-divergence rate: `{float(row['pre_divergence_rate']) * 100:.2f}%`")
        lines.append(f"- Pre-agent-shift rate: `{float(row['pre_agent_shift_rate']) * 100:.2f}%`")
        lines.append(f"- Median gas/channel lead: `{float(row['median_gas_lead_blocks']):.2f}` blocks")
        lines.append(f"- Mean gas/channel lead: `{float(row['mean_gas_lead_blocks']):.2f}` blocks")
        lines.append(f"- P10/P90 gas lead: `{float(row['p10_gas_lead_blocks']):.2f}` / `{float(row['p90_gas_lead_blocks']):.2f}` blocks")
        lines.append(f"- Median agent lead: `{float(row['median_agent_lead_blocks']):.2f}` blocks")
        lines.append("")

        lines.append("## Execution Savings Across Transition Windows")
        lines.append("")
        lines.append("| Policy | Total cost proxy | SUPT reduction vs policy |")
        lines.append("|---|---:|---:|")
        lines.append(f"| Always execute | {float(row['total_always_cost']):.6f} | {float(row['supt_reduction_vs_always']) * 100:.2f}% |")
        lines.append(f"| Reactive CLUTCH-only | {float(row['total_reactive_cost']):.6f} | {float(row['supt_reduction_vs_reactive']) * 100:.2f}% |")
        lines.append(f"| Simple gas-threshold | {float(row['total_gas_threshold_cost']):.6f} | {float(row['supt_reduction_vs_gas_threshold']) * 100:.2f}% |")
        lines.append(f"| SUPT gradient agent | {float(row['total_supt_cost']):.6f} | baseline |")
        lines.append("")

        lines.append("## Failure Modes")
        lines.append("")
        lines.append(f"- False EARLY_CAUTION/CAUTION without CLUTCH: `{int(row['false_early_caution_count'])}`")
        lines.append(f"- CLUTCH without prior gas/base-fee divergence: `{int(row['clutch_without_prior_divergence_count'])}`")
        lines.append(f"- CLUTCH without prior agent shift: `{int(row['clutch_without_prior_agent_shift_count'])}`")
        lines.append("")

        lines.append("## Event Table")
        lines.append("")

        display_cols = [
            "event_id",
            "clutch_block",
            "gas_channel_lead_blocks",
            "agent_lead_blocks",
            "had_pre_divergence",
            "had_pre_agent_shift",
            "at_clutch_agent_state",
            "at_clutch_agent_mode",
            "future_bad_after_clutch",
            "supt_reduction_vs_reactive",
            "supt_reduction_vs_gas_threshold",
        ]
        display_cols = [c for c in display_cols if c in events.columns]
        lines.append(events[display_cols].to_markdown(index=False))
    else:
        lines.append("No CLUTCH transitions found yet in this dataset.")

    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append(
        "This is transition-window validation using proxy execution costs, not live PnL. "
        "It tests whether gas/channel divergence and near-threshold behavior give the agent "
        "a measurable early-decision edge before full CLUTCH confirmation."
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_transition_validation_from_env() -> None:
    input_path = os.getenv("TRANSITION_INPUT_PATH", "data/counterfactual_log.csv")
    events_csv = os.getenv("TRANSITION_EVENTS_CSV", "data/transition_events.csv")
    summary_csv = os.getenv("TRANSITION_SUMMARY_CSV", "data/transition_summary.csv")
    failures_csv = os.getenv("TRANSITION_FAILURES_CSV", "data/transition_failures.csv")
    report_md = os.getenv("TRANSITION_REPORT_MD", "data/transition_validation_report.md")

    df = _load_log(input_path)
    df = _add_policy_costs(df)

    crossings = _find_clutch_crossings(df)

    event_rows = []

    for _, row in crossings.iterrows():
        event_rows.append(
            _summarize_transition_event(
                event_id=len(event_rows) + 1,
                event_row=row,
                df=df,
            )
        )

    events = pd.DataFrame(event_rows)

    failures = _build_failure_modes(df, events) if not events.empty else pd.DataFrame()
    summary = _build_summary(events, df, failures)

    Path(events_csv).parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(events_csv, index=False)

    Path(summary_csv).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_csv, index=False)

    Path(failures_csv).parent.mkdir(parents=True, exist_ok=True)
    failures.to_csv(failures_csv, index=False)

    _write_report(
        events=events,
        summary=summary,
        failures=failures,
        output_path=report_md,
    )

    row = summary.iloc[0]

    print("=" * 80)
    print("Transition-specific validation complete")
    print("=" * 80)
    print(f"Input:      {input_path}")
    print(f"Events CSV: {events_csv}")
    print(f"Summary:    {summary_csv}")
    print(f"Failures:   {failures_csv}")
    print(f"Report:     {report_md}")
    print("-" * 80)
    print(f"Transitions: {int(row['transitions'])}")
    print(f"Block span:  {int(row['block_span'])}")
    print(f"Approx hrs:  {float(row['approx_hours_at_12s_blocks']):.2f}")

    if int(row["transitions"]) > 0:
        print(f"Gas lead median: {float(row['median_gas_lead_blocks']):.2f} blocks")
        print(f"SUPT vs reactive reduction: {float(row['supt_reduction_vs_reactive']) * 100:.2f}%")
        print(f"SUPT vs gas-threshold reduction: {float(row['supt_reduction_vs_gas_threshold']) * 100:.2f}%")

    print("=" * 80)
