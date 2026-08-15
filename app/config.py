from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class AppConfig:
    window_size: int
    alert_threshold: float
    mode: str
    refresh_interval_ms: int
    data_dir: str

    eth_rpc_primary_url: str
    eth_rpc_backup_urls: tuple[str, ...]
    rpc_timeout_seconds: int
    rpc_batch_size: int
    max_live_window: int

    api_enable_auth: bool
    api_key_header_name: str
    api_free_tier_rate_limit_per_hour: int
    api_paid_tier_rate_limit_per_hour: int

    service_name: str
    environment: str

    @property
    def eth_rpc_url(self) -> str:
        return self.eth_rpc_primary_url

    @property
    def rpc_urls(self) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()

        for url in (self.eth_rpc_primary_url, *self.eth_rpc_backup_urls):
            if url and url not in seen:
                urls.append(url)
                seen.add(url)

        return urls

    @classmethod
    def from_env(cls) -> "AppConfig":
        primary_url = (
            os.getenv("ETH_RPC_PRIMARY_URL")
            or os.getenv("ETH_RPC_URL", "")
        ).strip()

        backup_urls_numbered = [
            os.getenv("ETH_RPC_BACKUP_URL_1", "").strip(),
            os.getenv("ETH_RPC_BACKUP_URL_2", "").strip(),
            os.getenv("ETH_RPC_BACKUP_URL_3", "").strip(),
        ]
        backup_urls_csv = list(_split_csv(os.getenv("ETH_RPC_BACKUP_URLS")))

        backup_urls = tuple(
            url for url in [*backup_urls_numbered, *backup_urls_csv] if url
        )

        return cls(
            window_size=int(os.getenv("WINDOW_SIZE", "150")),
            alert_threshold=float(os.getenv("ALERT_THRESHOLD", "1.0")),
            mode=os.getenv("MODE", "simulation").strip().lower(),
            refresh_interval_ms=int(os.getenv("REFRESH_INTERVAL_MS", "12000")),
            data_dir=os.getenv("DATA_DIR", "data").strip(),

            eth_rpc_primary_url=primary_url,
            eth_rpc_backup_urls=backup_urls,
            rpc_timeout_seconds=int(os.getenv("RPC_TIMEOUT_SECONDS", "12")),
            rpc_batch_size=int(os.getenv("RPC_BATCH_SIZE", "25")),
            max_live_window=int(os.getenv("MAX_LIVE_WINDOW", "150")),

            api_enable_auth=_to_bool(os.getenv("API_ENABLE_AUTH"), default=False),
            api_key_header_name=os.getenv("API_KEY_HEADER_NAME", "X-SUPT-Key").strip(),
            api_free_tier_rate_limit_per_hour=int(
                os.getenv("API_FREE_TIER_RATE_LIMIT_PER_HOUR", "60")
            ),
            api_paid_tier_rate_limit_per_hour=int(
                os.getenv("API_PAID_TIER_RATE_LIMIT_PER_HOUR", "10000")
            ),

            service_name=os.getenv("SERVICE_NAME", "SUPT Live Monitor").strip(),
            environment=os.getenv("ENVIRONMENT", "development").strip().lower(),
        )
