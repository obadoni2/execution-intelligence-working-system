from __future__ import annotations
from app.api.decision_api import router as decision_router
from app.api.execution_guidance import router as execution_guidance_router
from app.api.decision_history import router as decision_history_router
from app.api.decision_outcomes import router as decision_outcomes_router
from app.api.spy_validation_summary import router as spy_validation_summary_router
from app.api.spy_provider_audit import router as spy_provider_audit_router
from app.api.spy_discrimination import router as spy_discrimination_router
from app.api.spy_lead_lag import router as spy_lead_lag_router
from app.api.spy_lead_lag_hardening import router as spy_lead_lag_hardening_router
from app.api.spy_baseline_risk import router as spy_baseline_risk_router
from app.api.spy_precursor_confidence import router as spy_precursor_confidence_router

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI

from app.config import AppConfig
from app.live_eth import EthereumMonitorClient
from app.storage import get_latest_history_row, get_mode_alert_state


APP_STARTED_AT = datetime.now(timezone.utc)


def _provider_label(url: str) -> str:
    if not url:
        return "N/A"
    parsed = urlparse(url)
    return parsed.netloc or url


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def create_app() -> FastAPI:
    config = AppConfig.from_env()

    app = FastAPI(
        title=config.service_name,
        version="0.1.0",
        description="SUPT Live Monitor API",
    )

    app.include_router(decision_router)
    app.include_router(execution_guidance_router)
    app.include_router(decision_history_router)
    app.include_router(decision_outcomes_router)
    app.include_router(spy_validation_summary_router)
    app.include_router(spy_provider_audit_router)
    app.include_router(spy_discrimination_router)
    app.include_router(spy_lead_lag_router)
    app.include_router(spy_lead_lag_hardening_router)
    app.include_router(spy_baseline_risk_router)
    app.include_router(spy_precursor_confidence_router)

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "service": config.service_name,
            "environment": config.environment,
            "docs": "/docs",
            "health": "/v1/health",
            "current": "/v1/current",
        }

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        checked_at = datetime.now(timezone.utc)
        uptime_seconds = int((checked_at - APP_STARTED_AT).total_seconds())

        rpc_urls = getattr(config, "rpc_urls", [])
        client = EthereumMonitorClient(rpc_urls=rpc_urls)

        latest_block = None
        rpc_error = None
        rpc_ready = False

        try:
            latest_block, rpc_error = client._get_latest_block()
            rpc_ready = rpc_error is None and latest_block is not None
        except Exception as exc:
            rpc_error = f"{type(exc).__name__}: {exc}"
            rpc_ready = False

        active_provider = getattr(client, "active_rpc_url", "")
        primary_provider = rpc_urls[0] if rpc_urls else ""
        fallback_active = bool(
            rpc_ready and active_provider and primary_provider and active_provider != primary_provider
        )

        alert_state = get_mode_alert_state(config.data_dir, config.mode)
        latest_record = get_latest_history_row(config.data_dir, mode=config.mode)

        status = "ok" if rpc_ready else "degraded"

        return {
            "status": status,
            "checked_at": checked_at.isoformat(),
            "uptime_seconds": uptime_seconds,
            "service": {
                "name": config.service_name,
                "environment": config.environment,
                "mode": config.mode,
            },
            "monitor": {
                "window_size": config.window_size,
                "alert_threshold": config.alert_threshold,
                "data_dir": config.data_dir,
            },
            "rpc": {
                "ready": rpc_ready,
                "primary_provider": _provider_label(primary_provider),
                "active_provider": _provider_label(active_provider),
                "fallback_active": fallback_active,
                "configured_providers": [_provider_label(url) for url in rpc_urls],
                "latest_block": latest_block,
                "error": rpc_error,
            },
            "alert": {
                "is_active": bool(alert_state.get("is_active", False)),
                "alert_id": alert_state.get("alert_id"),
                "started_at": alert_state.get("started_at"),
                "started_block": alert_state.get("started_block"),
                "last_dij": alert_state.get("last_dij"),
                "last_regime": alert_state.get("last_regime"),
                "last_message": alert_state.get("last_message"),
            },
            "latest_record": _json_safe(latest_record) if latest_record else None,
        }

    @app.get("/v1/current")
    def current() -> dict[str, Any]:
        latest_record = get_latest_history_row(config.data_dir, mode=config.mode)
        alert_state = get_mode_alert_state(config.data_dir, config.mode)

        if latest_record is None:
            return {
                "status": "no_data",
                "mode": config.mode,
                "message": "No monitor records found yet.",
            }

        return {
            "status": "ok",
            "service": config.service_name,
            "environment": config.environment,
            "mode": config.mode,
            "pipeline_version": "supt-frozen-1.0",
            "chain": "eth",
            "timestamp": _json_safe(latest_record.get("timestamp")),
            "latest_block": latest_record.get("latest_block"),
            "window_size": latest_record.get("window_size"),
            "threshold": latest_record.get("threshold"),
            "regime": latest_record.get("regime"),
            "d_ij": {
                "composite": latest_record.get("dij"),
                "tx_count": latest_record.get("dij"),
                "gas": latest_record.get("gas_dij"),
                "base_fee": latest_record.get("base_fee_dij"),
            },
            "tx_stats": {
                "mean": latest_record.get("mean_tx_count"),
                "std": latest_record.get("std_tx_count"),
            },
            "alert": {
                "is_active": bool(alert_state.get("is_active", False)),
                "alert_id": alert_state.get("alert_id"),
                "started_at": alert_state.get("started_at"),
                "started_block": alert_state.get("started_block"),
                "last_message": alert_state.get("last_message"),
            },
            "note": latest_record.get("note"),
        }

    return app


app = create_app()
app = create_app()
