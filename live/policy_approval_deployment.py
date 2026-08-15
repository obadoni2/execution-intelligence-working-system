from __future__ import annotations

import csv
from pathlib import Path


VERSIONS = Path("live/data/policy_versions.csv")
TRUST = Path("live/data/policy_trust_score.csv")
DRIFT = Path("live/data/policy_drift_monitor.csv")
OUT = Path("live/data/policy_approval_deployment.csv")


def load_csv(path):
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


def fnum(v, default=0.0):
    try:
        return float(v)
    except:
        return default


def determine_stage(
    trust_score,
    trust_label,
    total_events,
    drift_score,
):
    if trust_label == "UNTRUSTED":
        return "DRAFT"

    if total_events < 25:
        return "SIMULATION"

    if total_events < 50:
        return "PAPER_TRADING"

    if (
        trust_score >= 0.70
        and drift_score < 0.30
        and total_events >= 50
    ):
        return "LIMITED_LIVE"

    if (
        trust_score >= 0.85
        and drift_score < 0.20
        and total_events >= 100
    ):
        return "PRODUCTION"

    return "PAPER_TRADING"


def deployment_percent(stage):
    mapping = {
        "DRAFT": 0,
        "SIMULATION": 0,
        "PAPER_TRADING": 0,
        "LIMITED_LIVE": 5,
        "PRODUCTION": 100,
    }
    return mapping.get(stage, 0)


def rollback_rule(stage):
    if stage == "PRODUCTION":
        return "ROLLBACK_IF_TRUST_DROPS_OR_DRIFT_SPIKES"

    if stage == "LIMITED_LIVE":
        return "ROLLBACK_IF_PERFORMANCE_DEGRADES"

    return "NOT_DEPLOYED"


def main():
    versions = load_csv(VERSIONS)
    trust = load_csv(TRUST)
    drift = load_csv(DRIFT)

    if not versions:
        raise FileNotFoundError(VERSIONS)

    if not trust:
        raise FileNotFoundError(TRUST)

    if not drift:
        raise FileNotFoundError(DRIFT)

    version = versions[-1]
    trust_row = trust[-1]
    drift_row = drift[-1]

    trust_score = fnum(
        trust_row.get("policy_trust_score")
    )

    trust_label = trust_row.get(
        "policy_trust_label",
        "UNTRUSTED",
    )

    total_events = int(
        fnum(trust_row.get("total_events"))
    )

    drift_score = fnum(
        drift_row.get("drift_score")
    )

    stage = determine_stage(
        trust_score,
        trust_label,
        total_events,
        drift_score,
    )

    row = {
        "policy_id":
            version["policy_id"],
        "policy_version":
            version["policy_version"],
        "deployment_stage":
            stage,
        "capital_percentage":
            deployment_percent(stage),
        "trust_label":
            trust_label,
        "trust_score":
            round(trust_score, 6),
        "total_events":
            total_events,
        "drift_score":
            round(drift_score, 6),
        "rollback_rule":
            rollback_rule(stage),
        "approval_status":
            "PENDING_REVIEW",
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(row.keys()),
        )

        writer.writeheader()
        writer.writerow(row)

    print(
        "POLICY APPROVAL ENGINE COMPLETE"
    )

    print(row)

    print(
        f"Wrote row to {OUT}"
    )


if __name__ == "__main__":
    main()
