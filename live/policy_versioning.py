from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


TRUST = Path("live/data/policy_trust_score.csv")
RECAL = Path("live/data/automatic_policy_recalibration.csv")
OUT = Path("live/data/policy_versions.csv")


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


def policy_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def deployment_stage(trust_label: str, recommended_updates: int) -> str:
    if trust_label in {"UNTRUSTED", "LOW_TRUST"}:
        return "DRAFT"
    if recommended_updates == 0:
        return "SIMULATION"
    if trust_label == "MODERATE_TRUST":
        return "PAPER_TRADING"
    if trust_label == "HIGH_TRUST":
        return "LIMITED_LIVE"
    if trust_label == "PRODUCTION_READY":
        return "PRODUCTION_REVIEW"
    return "DRAFT"


def rollback_rule(trust_label: str, trust_score: float, updates: int) -> str:
    if trust_label == "UNTRUSTED":
        return "ROLLBACK_REQUIRED_IF_DEPLOYED"
    if trust_score < 0.50:
        return "DO_NOT_DEPLOY"
    if updates > 0:
        return "REQUIRE_MANUAL_REVIEW"
    return "NO_ROLLBACK_TRIGGER"


def main() -> None:
    trust_rows = load_csv(TRUST)
    recal_rows = load_csv(RECAL)

    if not trust_rows:
        raise FileNotFoundError(f"No policy trust score found at {TRUST}")

    if not recal_rows:
        raise FileNotFoundError(f"No recalibration rows found at {RECAL}")

    trust = trust_rows[-1]

    trust_label = trust.get("policy_trust_label", "UNTRUSTED")
    trust_score = fnum(trust.get("policy_trust_score"))
    total_events = int(fnum(trust.get("total_events")))

    updates = [r for r in recal_rows if r.get("recommended_update") != "NO_CHANGE"]
    recommended_updates = len(updates)

    created_at = datetime.now(timezone.utc).isoformat()

    payload = f"{created_at}|{trust_label}|{trust_score}|{recommended_updates}|{total_events}"
    version_hash = policy_hash(payload)

    version = {
        "created_at": created_at,
        "policy_id": f"POLICY_{version_hash}",
        "policy_version": "v1.0-candidate",
        "policy_status": "CANDIDATE",
        "deployment_stage": deployment_stage(trust_label, recommended_updates),
        "trust_label": trust_label,
        "trust_score": round(trust_score, 6),
        "total_events": total_events,
        "recommended_updates": recommended_updates,
        "rollback_rule": rollback_rule(trust_label, trust_score, recommended_updates),
        "approval_required": "TRUE",
        "deployment_mode": "SAFE_REGISTRY_ONLY",
        "notes": (
            "This policy version is registered for tracking only. "
            "No live deployment should happen without manual review, "
            "paper validation, and rollback readiness."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    exists = OUT.exists()

    with OUT.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(version.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(version)

    print("POLICY VERSION REGISTERED")
    print(version)
    print(f"Wrote policy version to {OUT}")


if __name__ == "__main__":
    main()

