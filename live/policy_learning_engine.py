from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


COUNTERFACTUAL = Path("live/data/counterfactual_value_analysis.csv")
RISK_GATE = Path("live/data/live_risk_gate_receipts.csv")
OUT = Path("live/data/policy_learning_recommendations.csv")

MIN_SAMPLES_FOR_CONFIDENCE = 20


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest_by_symbol(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest = {}
    for row in rows:
        symbol = row.get("symbol")
        if symbol:
            latest[symbol] = row
    return latest


def action_stats(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        action = row.get("risk_decision", "UNKNOWN")
        grouped.setdefault(action, []).append(row)

    stats = {}

    for action, action_rows in grouped.items():
        values = [fnum(r.get("net_policy_advantage")) for r in action_rows]
        positive = sum(1 for r in action_rows if r.get("counterfactual_label") == "POLICY_BETTER_THAN_BASELINE")
        negative = sum(1 for r in action_rows if r.get("counterfactual_label") == "BASELINE_BETTER_THAN_POLICY")

        n = len(action_rows)
        avg_value = sum(values) / n if n else 0.0
        positive_rate = positive / n if n else 0.0
        negative_rate = negative / n if n else 0.0

        sample_confidence = min(n / MIN_SAMPLES_FOR_CONFIDENCE, 1.0)

        # Robust score penalizes low samples and negative outcomes.
        robust_score = (
            (0.55 * avg_value)
            + (0.30 * positive_rate)
            - (0.25 * negative_rate)
        ) * sample_confidence

        stats[action] = {
            "samples": n,
            "avg_net_policy_advantage": round(avg_value, 6),
            "positive_rate": round(positive_rate, 6),
            "negative_rate": round(negative_rate, 6),
            "sample_confidence": round(sample_confidence, 6),
            "robust_policy_score": round(robust_score, 6),
        }

    return stats


def symbol_action_stats(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        symbol = row.get("symbol", "UNKNOWN")
        grouped.setdefault(symbol, []).append(row)

    return {symbol: action_stats(symbol_rows) for symbol, symbol_rows in grouped.items()}


def choose_action(global_stats: Dict[str, Dict[str, Any]], symbol_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    actions = ["ALLOW", "REDUCE_SIZE", "PAUSE", "BLOCK"]
    candidates = []

    for action in actions:
        g = global_stats.get(action, {})
        s = symbol_stats.get(action, {})

        global_score = fnum(g.get("robust_policy_score"))
        symbol_score = fnum(s.get("robust_policy_score"))

        global_samples = int(fnum(g.get("samples")))
        symbol_samples = int(fnum(s.get("samples")))

        # Blend symbol-specific learning with global policy learning.
        if symbol_samples >= MIN_SAMPLES_FOR_CONFIDENCE:
            blended_score = (0.65 * symbol_score) + (0.35 * global_score)
            reason = "SYMBOL_HISTORY_STRONG"
        elif symbol_samples > 0:
            blended_score = (0.35 * symbol_score) + (0.65 * global_score)
            reason = "SYMBOL_HISTORY_WEAK_GLOBAL_WEIGHTED"
        else:
            blended_score = global_score
            reason = "GLOBAL_POLICY_ONLY"

        candidates.append({
            "action": action,
            "blended_score": round(blended_score, 6),
            "global_samples": global_samples,
            "symbol_samples": symbol_samples,
            "reason": reason,
        })

    candidates.sort(key=lambda x: x["blended_score"], reverse=True)
    best = candidates[0]

    if best["blended_score"] <= 0:
        return {
            "learned_action": "KEEP_CURRENT_RULES",
            "learned_confidence": "LOW",
            "learned_score": best["blended_score"],
            "learning_reason": "NO_ACTION_HAS_POSITIVE_ROBUST_SCORE",
            "ranked_actions": candidates,
        }

    confidence = "HIGH" if best["blended_score"] >= 0.5 else "MEDIUM" if best["blended_score"] >= 0.15 else "LOW"

    return {
        "learned_action": best["action"],
        "learned_confidence": confidence,
        "learned_score": best["blended_score"],
        "learning_reason": best["reason"],
        "ranked_actions": candidates,
    }


def run() -> List[Dict[str, Any]]:
    cf_rows = load_csv(COUNTERFACTUAL)
    risk_rows = load_csv(RISK_GATE)

    if not cf_rows:
        raise FileNotFoundError(f"No counterfactual rows found at {COUNTERFACTUAL}")

    if not risk_rows:
        raise FileNotFoundError(f"No risk-gate rows found at {RISK_GATE}")

    global_stats = action_stats(cf_rows)
    by_symbol_stats = symbol_action_stats(cf_rows)
    latest_risk = latest_by_symbol(risk_rows)

    outputs = []

    for symbol, risk in latest_risk.items():
        symbol_stats = by_symbol_stats.get(symbol, {})
        decision = choose_action(global_stats, symbol_stats)

        outputs.append({
            "symbol": symbol,
            "current_regime": risk.get("regime"),
            "current_guidance": risk.get("guidance"),
            "current_risk_decision": risk.get("risk_decision"),
            "current_stress_score": risk.get("stress_score"),
            "spread_bps": risk.get("spread_bps"),
            "top_depth": risk.get("top_depth"),
            "trade_imbalance": risk.get("trade_imbalance"),
            "learned_action": decision["learned_action"],
            "learned_confidence": decision["learned_confidence"],
            "learned_score": decision["learned_score"],
            "learning_reason": decision["learning_reason"],
            "global_action_stats": str(global_stats),
            "symbol_action_stats": str(symbol_stats),
            "provider_data_hash": risk.get("provider_data_hash"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outputs[0].keys()))
        writer.writeheader()
        writer.writerows(outputs)

    return outputs


def main() -> None:
    rows = run()
    print("POLICY LEARNING ENGINE COMPLETE")
    print(f"Wrote {len(rows)} policy recommendations to {OUT}")

    for r in rows:
        print(
            f"{r['symbol']}: current={r['current_risk_decision']} "
            f"learned={r['learned_action']} confidence={r['learned_confidence']} "
            f"score={r['learned_score']}"
        )


if __name__ == "__main__":
    main()
