from __future__ import annotations

import json
import math
import os
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ALPHA = 0.01
TAIL_N = 50
DEFAULT_WINDOW = int(os.getenv("MULTICHAIN_WINDOW_SIZE", "150"))

ETH_RPC_URL = os.getenv("ETH_RPC_PRIMARY_URL", "https://ethereum-rpc.publicnode.com")
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
BTC_MEMPOOL_API_URL = os.getenv("BTC_MEMPOOL_API_URL", "https://mempool.space/api")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
ALERT_LOG_PATH = DATA_DIR / "multichain_alerts.jsonl"


@dataclass
class ChainState:
    chain: str
    timestamp: str
    height: int
    metric_name: str
    metric_value: float
    d_ij: float
    regime: str
    notes: str = ""


@dataclass
class MultiChainSnapshot:
    timestamp: str
    ethereum: Optional[ChainState]
    base: Optional[ChainState]
    bitcoin: Optional[ChainState]
    solana: Optional[ChainState]
    cross_chain_divergence: float
    divergence_regime: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _rpc_call(url: str, method: str, params: Optional[list] = None, timeout: int = 20) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }

    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"RPC error from {url}: {data['error']}")

    return data.get("result")


def _hex_to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def _mean(values: List[float], default: float = 0.0) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if not clean:
        return default
    return float(sum(clean) / len(clean))


def _std(values: List[float], default: float = 0.0) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if len(clean) < 2:
        return default
    return float(statistics.pstdev(clean))


def compute_dij(values: List[float], alpha: float = ALPHA, tail_n: int = TAIL_N) -> float:
    """
    Lightweight SUPT-style coherence/stress score.

    This does not claim biological consciousness or prediction.
    It reads structural deviation in a metric window.

    Lower values = calmer / coherent.
    Higher values = more stressed / divergent.
    """
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]

    if len(clean) < 5:
        return 0.0

    window = clean[-tail_n:] if len(clean) >= tail_n else clean
    baseline = clean[:-tail_n] if len(clean) > tail_n else clean

    mu = _mean(baseline)
    sigma = _std(baseline)

    if sigma <= 1e-9:
        sigma = max(abs(mu) * alpha, 1e-9)

    latest = window[-1]
    z = abs(latest - mu) / sigma

    trend = 0.0
    if len(window) >= 2:
        trend = abs(window[-1] - window[0]) / sigma

    dij = 0.75 * z + 0.25 * trend
    return round(float(dij), 6)


def classify_regime(d_ij: float) -> str:
    if d_ij >= 1.20:
        return "HIGH_STRESS"
    if d_ij >= 1.00:
        return "CLUTCH"
    if d_ij >= 0.85:
        return "CAUTION"
    return "COHERENCE"


def fetch_evm_block_window(rpc_url: str, chain: str, window_size: int = DEFAULT_WINDOW) -> ChainState:
    latest_hex = _rpc_call(rpc_url, "eth_blockNumber")
    latest = _hex_to_int(latest_hex)

    gas_ratios: List[float] = []

    start = max(0, latest - window_size + 1)

    for block_number in range(start, latest + 1):
        block_hex = hex(block_number)
        block = _rpc_call(rpc_url, "eth_getBlockByNumber", [block_hex, False])

        if not block:
            continue

        gas_used = _hex_to_int(block.get("gasUsed"))
        gas_limit = _hex_to_int(block.get("gasLimit"))

        if gas_limit > 0:
            gas_ratios.append(gas_used / gas_limit)

    d_ij = compute_dij(gas_ratios)
    regime = classify_regime(d_ij)
    latest_metric = gas_ratios[-1] if gas_ratios else 0.0

    return ChainState(
        chain=chain,
        timestamp=_now_iso(),
        height=latest,
        metric_name="gas_used_ratio",
        metric_value=round(latest_metric, 6),
        d_ij=d_ij,
        regime=regime,
        notes=f"{len(gas_ratios)} EVM blocks sampled",
    )


def fetch_bitcoin_state(window_size: int = DEFAULT_WINDOW) -> ChainState:
    tip_resp = requests.get(f"{BTC_MEMPOOL_API_URL}/blocks/tip/height", timeout=20)
    tip_resp.raise_for_status()
    tip_height = _safe_int(tip_resp.text)

    blocks_resp = requests.get(f"{BTC_MEMPOOL_API_URL}/v1/blocks", timeout=20)
    blocks_resp.raise_for_status()
    blocks = blocks_resp.json()

    tx_counts: List[float] = []
    for block in blocks[: min(len(blocks), window_size)]:
        tx_count = _safe_float(block.get("tx_count"))
        if tx_count > 0:
            tx_counts.append(tx_count)

    tx_counts = list(reversed(tx_counts))

    d_ij = compute_dij(tx_counts)
    regime = classify_regime(d_ij)
    latest_metric = tx_counts[-1] if tx_counts else 0.0

    return ChainState(
        chain="bitcoin",
        timestamp=_now_iso(),
        height=tip_height,
        metric_name="tx_count",
        metric_value=round(latest_metric, 6),
        d_ij=d_ij,
        regime=regime,
        notes=f"{len(tx_counts)} BTC blocks sampled from mempool.space",
    )


def fetch_bitcoin_mempool_depth() -> Dict[str, Any]:
    resp = requests.get(f"{BTC_MEMPOOL_API_URL}/mempool", timeout=20)
    resp.raise_for_status()
    data = resp.json()

    return {
        "count": _safe_int(data.get("count")),
        "vsize": _safe_int(data.get("vsize")),
        "total_fee": _safe_int(data.get("total_fee")),
    }


def fetch_solana_state(window_size: int = DEFAULT_WINDOW) -> ChainState:
    slot = _safe_int(_rpc_call(SOLANA_RPC_URL, "getSlot"))

    samples = _rpc_call(SOLANA_RPC_URL, "getRecentPerformanceSamples", [min(window_size, 720)])

    tps_values: List[float] = []

    for item in samples or []:
        num_tx = _safe_float(item.get("numTransactions"))
        sample_period = _safe_float(item.get("samplePeriodSecs"))

        if sample_period > 0:
            tps_values.append(num_tx / sample_period)

    tps_values = list(reversed(tps_values))

    d_ij = compute_dij(tps_values)
    regime = classify_regime(d_ij)
    latest_metric = tps_values[-1] if tps_values else 0.0

    return ChainState(
        chain="solana",
        timestamp=_now_iso(),
        height=slot,
        metric_name="tps",
        metric_value=round(latest_metric, 6),
        d_ij=d_ij,
        regime=regime,
        notes=f"{len(tps_values)} Solana performance samples",
    )


def compute_cross_chain_divergence(states: List[Optional[ChainState]]) -> float:
    valid = [s.d_ij for s in states if s is not None and math.isfinite(s.d_ij)]

    if len(valid) < 2:
        return 0.0

    return round(max(valid) - min(valid), 6)


def classify_divergence(value: float) -> str:
    if value >= 0.75:
        return "HIGH_DIVERGENCE"
    if value >= 0.40:
        return "MODERATE_DIVERGENCE"
    if value >= 0.20:
        return "LOW_DIVERGENCE"
    return "ALIGNED"


def write_alert_log(snapshot: MultiChainSnapshot) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp": snapshot.timestamp,
        "cross_chain_divergence": snapshot.cross_chain_divergence,
        "divergence_regime": snapshot.divergence_regime,
        "ethereum": asdict(snapshot.ethereum) if snapshot.ethereum else None,
        "base": asdict(snapshot.base) if snapshot.base else None,
        "bitcoin": asdict(snapshot.bitcoin) if snapshot.bitcoin else None,
        "solana": asdict(snapshot.solana) if snapshot.solana else None,
    }

    with ALERT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def safe_probe(name: str, fn) -> Optional[ChainState]:
    try:
        return fn()
    except Exception as exc:
        print(f"[WARN] {name} probe failed: {exc}")
        return None


def run_snapshot(window_size: int = DEFAULT_WINDOW, write_log: bool = True) -> MultiChainSnapshot:
    ethereum = safe_probe(
        "ethereum",
        lambda: fetch_evm_block_window(ETH_RPC_URL, "ethereum", window_size),
    )

    base = safe_probe(
        "base",
        lambda: fetch_evm_block_window(BASE_RPC_URL, "base", window_size),
    )

    bitcoin = safe_probe(
        "bitcoin",
        lambda: fetch_bitcoin_state(window_size),
    )

    solana = safe_probe(
        "solana",
        lambda: fetch_solana_state(window_size),
    )

    divergence = compute_cross_chain_divergence([ethereum, base, bitcoin, solana])
    divergence_regime = classify_divergence(divergence)

    snapshot = MultiChainSnapshot(
        timestamp=_now_iso(),
        ethereum=ethereum,
        base=base,
        bitcoin=bitcoin,
        solana=solana,
        cross_chain_divergence=divergence,
        divergence_regime=divergence_regime,
    )

    if write_log:
        write_alert_log(snapshot)

    return snapshot


def snapshot_to_dict(snapshot: MultiChainSnapshot) -> Dict[str, Any]:
    return {
        "timestamp": snapshot.timestamp,
        "cross_chain_divergence": snapshot.cross_chain_divergence,
        "divergence_regime": snapshot.divergence_regime,
        "ethereum": asdict(snapshot.ethereum) if snapshot.ethereum else None,
        "base": asdict(snapshot.base) if snapshot.base else None,
        "bitcoin": asdict(snapshot.bitcoin) if snapshot.bitcoin else None,
        "solana": asdict(snapshot.solana) if snapshot.solana else None,
    }


def main() -> None:
    print("SUPT Multi-Chain Monitor")
    print(f"window_size={DEFAULT_WINDOW}, alpha={ALPHA}, tail_n={TAIL_N}")
    print("-" * 80)

    snapshot = run_snapshot(DEFAULT_WINDOW, write_log=True)
    print(json.dumps(snapshot_to_dict(snapshot), indent=2))


if __name__ == "__main__":
    main()
