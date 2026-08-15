from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

_BLOCK_CACHE: dict[str, list[dict[str, Any]]] = {}


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        clean = url.strip()
        if clean and clean not in seen:
            ordered.append(clean)
            seen.add(clean)
    return ordered


class EthereumMonitorClient:
    def __init__(self, rpc_url: str | None = None, rpc_urls: list[str] | tuple[str, ...] | None = None) -> None:
        self.timeout = int(os.getenv("RPC_TIMEOUT_SECONDS", "12"))
        self.max_live_window = int(os.getenv("MAX_LIVE_WINDOW", "150"))
        self.batch_size = int(os.getenv("RPC_BATCH_SIZE", "25"))

        env_primary = (os.getenv("ETH_RPC_PRIMARY_URL") or os.getenv("ETH_RPC_URL", "")).strip()
        env_backups = [
            os.getenv("ETH_RPC_BACKUP_URL_1", "").strip(),
            os.getenv("ETH_RPC_BACKUP_URL_2", "").strip(),
            os.getenv("ETH_RPC_BACKUP_URL_3", "").strip(),
        ]
        env_backups.extend(list(_split_csv(os.getenv("ETH_RPC_BACKUP_URLS"))))

        if rpc_urls:
            urls = [str(url).strip() for url in rpc_urls if str(url).strip()]
        elif rpc_url:
            urls = [rpc_url.strip(), *env_backups]
        else:
            urls = [env_primary, *env_backups]

        self.rpc_urls = _dedupe_urls(urls)
        self.active_rpc_url = self.rpc_urls[0] if self.rpc_urls else ""
        self.cache_key = "|".join(self.rpc_urls)

    def get_effective_window(self, requested_window: int) -> int:
        return min(requested_window, self.max_live_window)

    def _ordered_rpc_urls(self) -> list[str]:
        if not self.rpc_urls:
            return []

        if self.active_rpc_url and self.active_rpc_url in self.rpc_urls:
            return [self.active_rpc_url] + [url for url in self.rpc_urls if url != self.active_rpc_url]

        return list(self.rpc_urls)

    def _rpc_post(self, payload: Any, rpc_url: str) -> Any:
        response = requests.post(
            rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _call_with_failover(self, payload: Any, purpose: str) -> tuple[Any | None, str | None]:
        errors: list[str] = []

        for rpc_url in self._ordered_rpc_urls():
            try:
                result = self._rpc_post(payload, rpc_url)

                if self.active_rpc_url != rpc_url:
                    print(f"[live_eth] failover switch -> {rpc_url} for {purpose}")

                self.active_rpc_url = rpc_url
                return result, None

            except requests.Timeout:
                errors.append(f"{rpc_url}: timeout")
                print(f"[live_eth] provider timeout on {rpc_url} during {purpose}")
            except requests.RequestException as exc:
                errors.append(f"{rpc_url}: {exc}")
                print(f"[live_eth] provider request error on {rpc_url} during {purpose}: {exc}")
            except Exception as exc:
                errors.append(f"{rpc_url}: {type(exc).__name__}: {exc}")
                print(f"[live_eth] provider error on {rpc_url} during {purpose}: {exc}")

        if not errors:
            return None, "No RPC URLs configured."

        return None, "All RPC providers failed. " + " | ".join(errors)

    @staticmethod
    def _hex_to_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("0x"):
                return int(value, 16)
            return int(value)
        return default

    @staticmethod
    def _normalize_block(block: dict[str, Any], fallback_number: int, rpc_provider: str) -> dict[str, Any]:
        txs = block.get("transactions", [])
        tx_count = len(txs)

        gas_used_raw = block.get("gasUsed")
        if isinstance(gas_used_raw, str) and gas_used_raw.startswith("0x"):
            gas_used = int(gas_used_raw, 16)
        else:
            gas_used = int(gas_used_raw or 0)

        base_fee_raw = block.get("baseFeePerGas")
        if base_fee_raw is None:
            base_fee_gwei = None
        else:
            if isinstance(base_fee_raw, str) and base_fee_raw.startswith("0x"):
                base_fee_wei = int(base_fee_raw, 16)
            else:
                base_fee_wei = int(base_fee_raw)
            base_fee_gwei = float(base_fee_wei) / 1e9

        timestamp_raw = block.get("timestamp")
        if isinstance(timestamp_raw, str) and timestamp_raw.startswith("0x"):
            timestamp = int(timestamp_raw, 16)
        else:
            timestamp = int(timestamp_raw or 0)

        number_raw = block.get("number")
        if isinstance(number_raw, str) and number_raw.startswith("0x"):
            block_number = int(number_raw, 16)
        else:
            block_number = int(number_raw or fallback_number)

        timestamp_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

        return {
            "number": block_number,
            "timestamp": timestamp,
            "timestamp_iso": timestamp_iso,
            "tx_count": tx_count,
            "gas_used": gas_used,
            "base_fee_gwei": base_fee_gwei,
            "rpc_provider": rpc_provider,
        }

    def _get_latest_block(self) -> tuple[int | None, str | None]:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1,
        }

        result, error = self._call_with_failover(payload, purpose="latest_block")
        if error is not None:
            return None, error

        if not isinstance(result, dict):
            return None, "Unexpected eth_blockNumber response format."

        if result.get("error") is not None:
            return None, f"eth_blockNumber RPC error: {result['error']}"

        latest_block = self._hex_to_int(result.get("result"), default=-1)
        if latest_block < 0:
            return None, "Invalid latest block number response."

        return latest_block, None

    def is_ready(self) -> bool:
        latest_block, error = self._get_latest_block()
        return error is None and latest_block is not None

    def _fetch_block_range(self, start_block: int, end_block: int) -> tuple[list[dict[str, Any]], str | None]:
        if end_block < start_block:
            return [], None

        block_numbers = list(range(start_block, end_block + 1))
        blocks: list[dict[str, Any]] = []

        for i in range(0, len(block_numbers), self.batch_size):
            chunk = block_numbers[i : i + self.batch_size]

            payload = [
                {
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [hex(number), False],
                    "id": number,
                }
                for number in chunk
            ]

            result, error = self._call_with_failover(
                payload,
                purpose=f"block_range_{chunk[0]}_{chunk[-1]}",
            )
            if error is not None:
                return [], error

            if not isinstance(result, list):
                return [], "Unexpected batch RPC response format."

            result_by_id = {item.get("id"): item for item in result}

            for number in chunk:
                item = result_by_id.get(number)

                if item is None:
                    print(f"[live_eth] missing RPC response for block {number}")
                    continue

                if item.get("error") is not None:
                    print(f"[live_eth] RPC error for block {number}: {item['error']}")
                    continue

                block = item.get("result")
                if not block:
                    print(f"[live_eth] empty block result for block {number}")
                    continue

                blocks.append(
                    self._normalize_block(
                        block,
                        fallback_number=number,
                        rpc_provider=self.active_rpc_url,
                    )
                )

            print(f"[live_eth] fetched batch {chunk[0]} -> {chunk[-1]} via {self.active_rpc_url}")

        blocks.sort(key=lambda x: x["number"])
        return blocks, None

    def _get_cached_blocks(self) -> list[dict[str, Any]]:
        cached = _BLOCK_CACHE.get(self.cache_key, [])
        return sorted(cached, key=lambda x: x["number"])

    def _set_cached_blocks(self, blocks: list[dict[str, Any]]) -> None:
        ordered = sorted(blocks, key=lambda x: x["number"])
        deduped: dict[int, dict[str, Any]] = {block["number"]: block for block in ordered}
        _BLOCK_CACHE[self.cache_key] = list(sorted(deduped.values(), key=lambda x: x["number"]))

    def fetch_recent_blocks(self, window_size: int) -> tuple[list[dict[str, Any]], str | None]:
        if not self.rpc_urls:
            return [], "No Ethereum RPC URLs configured."

        latest_block, error = self._get_latest_block()
        if error is not None or latest_block is None:
            return [], error or "Could not fetch latest Ethereum block."

        effective_window = self.get_effective_window(window_size)
        start_block = max(0, latest_block - effective_window + 1)

        print(
            f"[live_eth] connected=True latest_block={latest_block} "
            f"requested_window={window_size} effective_window={effective_window} "
            f"active_rpc={self.active_rpc_url}"
        )

        cached_blocks = self._get_cached_blocks()

        if cached_blocks:
            cached_first = cached_blocks[0]["number"]
            cached_last = cached_blocks[-1]["number"]
            print(f"[live_eth] cache range {cached_first} -> {cached_last} ({len(cached_blocks)} blocks)")
        else:
            print("[live_eth] cache empty")

        if cached_blocks:
            cached_numbers = {block["number"] for block in cached_blocks}
            needed_numbers = set(range(start_block, latest_block + 1))
            if needed_numbers.issubset(cached_numbers):
                blocks = [block for block in cached_blocks if start_block <= block["number"] <= latest_block]
                blocks = sorted(blocks, key=lambda x: x["number"])
                print(f"[live_eth] serving {len(blocks)} blocks fully from cache")
                return blocks, None

        if cached_blocks:
            cached_last = cached_blocks[-1]["number"]

            if cached_last < latest_block and cached_last >= start_block - 1:
                fetch_start = cached_last + 1
                print(f"[live_eth] incremental fetch {fetch_start} -> {latest_block}")
                new_blocks, error = self._fetch_block_range(fetch_start, latest_block)
                if error is not None:
                    return [], error

                merged = cached_blocks + new_blocks
                merged = [block for block in merged if start_block <= block["number"] <= latest_block]
                self._set_cached_blocks(merged)

                final_blocks = self._get_cached_blocks()
                final_blocks = [block for block in final_blocks if start_block <= block["number"] <= latest_block]
                if len(final_blocks) < 2:
                    return [], "Live RPC returned too few blocks to compute d_ij."

                print(f"[live_eth] serving {len(final_blocks)} blocks after incremental update")
                return final_blocks, None

        print(f"[live_eth] full fetch {start_block} -> {latest_block}")
        blocks, error = self._fetch_block_range(start_block, latest_block)
        if error is not None:
            return [], error

        if len(blocks) < 2:
            return [], "Live RPC returned too few blocks to compute d_ij."

        self._set_cached_blocks(blocks)
        print(f"[live_eth] serving {len(blocks)} blocks after full fetch")
        return blocks, None


def extract_metric_series(blocks: list[dict[str, Any]]) -> dict[str, list[float]]:
    tx_counts = [float(block["tx_count"]) for block in blocks]
    gas_used = [float(block["gas_used"]) for block in blocks if block.get("gas_used") is not None]
    base_fee_gwei = [
        float(block["base_fee_gwei"])
        for block in blocks
        if block.get("base_fee_gwei") is not None
    ]
    block_numbers = [int(block["number"]) for block in blocks]

    return {
        "block_numbers": block_numbers,
        "tx_counts": tx_counts,
        "gas_used": gas_used,
        "base_fee_gwei": base_fee_gwei,
    }