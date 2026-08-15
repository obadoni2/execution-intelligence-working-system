from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter


router = APIRouter(prefix="/v1", tags=["SPY Validation"])

RECEIPTS_PATH = Path("equities/data/spy_outcomes.csv")


def load_receipts() -> List[Dict[str, Any]]:
    if not RECEIPTS_PATH.exists():
        return []

    with RECEIPTS_PATH.open("r", encoding="utf-8") as f:
        clean_lines = [line for line in f if not line.startswith("#")]

    return list(csv.DictReader(clean_lines))


@router.get("/spy-validation-summary")
def spy_validation_summary() -> Dict[str, Any]:
    rows = load_receipts()

    total = len(rows)
    bad = [r for r in rows if r.get("is_bad") == "TRUE"]
    clean = [r for r in rows if r.get("is_bad") == "FALSE"]

    schema_hashes = sorted({r.get("schema_hash", "") for r in rows if r.get("schema_hash")})
    provider_hashes = sorted({r.get("provider_data_hash", "") for r in rows if r.get("provider_data_hash")})
    providers = sorted({r.get("provider", "") for r in rows if r.get("provider")})

    state_counts = Counter(r.get("decision_state", "UNKNOWN") for r in rows)
    state_bad_counts = Counter(r.get("decision_state", "UNKNOWN") for r in bad)

    state_summary = {}
    for state, count in state_counts.items():
        bad_count = state_bad_counts[state]
        state_summary[state] = {
            "total": count,
            "bad": bad_count,
            "clean": count - bad_count,
            "bad_rate": bad_count / count if count else 0.0,
        }

    rule_counter = Counter()
    for r in bad:
        rules = r.get("triggered_rules", "")
        if not rules:
            continue
        for rule in rules.split(","):
            rule = rule.strip()
            if rule:
                rule_counter[rule] += 1

    return {
        "schema_version": "supt.spy_validation_summary.v1",
        "source_file": str(RECEIPTS_PATH),
        "total_receipts": total,
        "bad_receipts": len(bad),
        "clean_receipts": len(clean),
        "bad_rate": len(bad) / total if total else 0.0,
        "schema_hashes": schema_hashes,
        "providers": providers,
        "provider_data_hashes": provider_hashes,
        "decision_state_summary": state_summary,
        "triggered_rule_counts": dict(rule_counter),
    }
