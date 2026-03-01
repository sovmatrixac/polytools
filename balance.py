"""CLI helper for querying a wallet's USDC ERC20 balance on EVM networks.

The script is primarily geared towards Polymarket's main network (Polygon),
using the canonical USDC.e collateral token. Optionally, it can also query
USDC on Base and Arbitrum.

在未显式提供 RPC URL 且未设置对应环境变量时，脚本会为所选网络依次尝试一小组
内置的公共 RPC 端点，选取第一个可连通的节点作为数据来源。

Usage examples
--------------

    # 使用 .env 中的 FUNDER_ADDRESS / USER_ADDRESS，默认 Polygon
    python balanece.py

    # 指定地址，默认 Polygon
    python balanece.py 0xYourWallet

    # 指定网络与 RPC
    python balanece.py 0xYourWallet --network polygon
    python balanece.py 0xYourWallet --network base --rpc-url https://base-mainnet.example

The module can also be imported and the :func:`get_usdc_balance` function
reused from other Python code.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from dotenv import load_dotenv

from positions import InvalidAddressError, _normalize_address, is_valid_evm_address  # type: ignore[attr-defined]


class RPCConfigError(RuntimeError):
    """Raised when RPC URL is missing or unreachable."""


@dataclass
class NetworkConfig:
    """Configuration for a single EVM network."""

    name: str
    chain_id: int
    usdc_address: str
    rpc_env_var: str


# Canonical USDC.e on Polygon used by Polymarket as collateral.
POLYGON_USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Canonical USDC on Base and Arbitrum. These are public contract addresses.
BASE_USDC_ADDRESS = "0x833589fCD6eDaC0C2142dE3916c1c1D6cBfA27F6"
ARBITRUM_USDC_ADDRESS = "0xaf88d065e77c8C2239327C5EDb3A432268e5831"

DEFAULT_NETWORK = "polygon"

NETWORKS: Dict[str, NetworkConfig] = {
    "polygon": NetworkConfig(
        name="polygon",
        chain_id=137,
        usdc_address=POLYGON_USDC_E_ADDRESS,
        rpc_env_var="POLYGON_RPC_URL",
    ),
    "base": NetworkConfig(
        name="base",
        chain_id=8453,
        usdc_address=BASE_USDC_ADDRESS,
        rpc_env_var="BASE_RPC_URL",
    ),
    "arbitrum": NetworkConfig(
        name="arbitrum",
        chain_id=42161,
        usdc_address=ARBITRUM_USDC_ADDRESS,
        rpc_env_var="ARBITRUM_RPC_URL",
    ),
}


PUBLIC_RPC_ENDPOINTS: Dict[str, Sequence[str]] = {
    # A small, conservative list of public mainnet endpoints for each network.
    "polygon": (
        "https://polygon-rpc.com",
        "https://polygon.llamarpc.com",
        "https://rpc.ankr.com/polygon",
        "https://1rpc.io/polygon",
    ),
    "base": (
        "https://mainnet.base.org",
        "https://base.llamarpc.com",
        "https://rpc.ankr.com/base",
    ),
    "arbitrum": (
        "https://arb1.arbitrum.io/rpc",
        "https://arbitrum.llamarpc.com",
        "https://rpc.ankr.com/arbitrum",
    ),
}


def _get_network_config(name: Optional[str]) -> NetworkConfig:
    """Return :class:`NetworkConfig` for the given network name.

    Network names are matched case-insensitively. If ``name`` is empty or
    ``None``, :data:`DEFAULT_NETWORK` is used.
    """

    normalized = (name or DEFAULT_NETWORK).strip().lower()
    if not normalized:
        normalized = DEFAULT_NETWORK

    cfg = NETWORKS.get(normalized)
    if cfg is None:
        supported = ", ".join(sorted(NETWORKS.keys()))
        raise ValueError(f"不支持的网络: {name!r}。当前支持: {supported}")
    return cfg


def _get_public_rpc_candidates(cfg: NetworkConfig) -> Sequence[str]:
    """Return a small list of built-in public RPC URLs for ``cfg``'s network.

    These are used as a safe fallback when neither an explicit ``--rpc-url``
    nor the corresponding environment variable is provided. Especially useful
    in builder 模式等无法预先配置环境变量的运行环境。
    """

    return PUBLIC_RPC_ENDPOINTS.get(cfg.name, ())


def _resolve_rpc_url(cfg: NetworkConfig, explicit_rpc_url: Optional[str]) -> Optional[str]:
    """Resolve the RPC URL from CLI argument or environment.

    Priority:

    1. ``explicit_rpc_url`` if provided and non-empty
    2. Environment variable specified by ``cfg.rpc_env_var``

    If both sources are absent, returns ``None`` so that the caller can fall
    back to built-in public RPC endpoints.
    """

    if explicit_rpc_url:
        url = explicit_rpc_url.strip()
        if url:
            return url

    env_url = os.getenv(cfg.rpc_env_var, "").strip()
    if env_url:
        return env_url

    # No explicit or env RPC URL configured; let caller decide how to fall back.
    return None


def get_usdc_balance(
    address: str,
    network: str = DEFAULT_NETWORK,
    rpc_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Query on-chain USDC balance for ``address`` on the given network.

    Parameters
    ----------
    address:
        EVM wallet address. Both ``0x``-prefixed and plain hex strings are
        accepted; the function normalizes and validates them using
        :func:`positions.is_valid_evm_address`.
    network:
        Logical network name. Defaults to ``"polygon"``. Supported values
        currently are ``"polygon"``, ``"base"`` and ``"arbitrum"``.
    rpc_url:
        Optional RPC URL. When omitted, the function first checks the
        environment variable associated with the selected network (for
        example ``POLYGON_RPC_URL``). If that is also missing, it falls back
        to a small built-in list of public RPC endpoints and uses the first
        one that is reachable.

    Returns
    -------
    dict
        A dictionary with the following keys:

        - ``address``: normalized wallet address
        - ``network``: logical network name
        - ``chain_id``: numeric chain ID
        - ``usdc_contract``: USDC ERC20 contract address
        - ``symbol``: token symbol (best effort, defaults to "USDC")
        - ``decimals``: token decimals (best effort, defaults to 6)
        - ``raw_balance``: integer ERC20 balance
        - ``balance``: human-readable float balance
    """

    # Normalize and validate address using the shared helper from positions.py
    normalized = _normalize_address(address)
    if not is_valid_evm_address(normalized):
        raise InvalidAddressError(f"钱包地址格式无效: {address!r}")

    cfg = _get_network_config(network)
    resolved_rpc_url = _resolve_rpc_url(cfg, rpc_url)

    try:
        from web3 import Web3  # type: ignore
    except ImportError as exc:  # pragma: no cover - 环境相关
        raise RuntimeError(
            "web3 未安装，无法查询链上余额。请先安装 web3，例如: pip install web3"
        ) from exc

    w3 = None

    # 1) 显式或环境变量提供的 RPC URL
    if resolved_rpc_url:
        w3 = Web3(Web3.HTTPProvider(resolved_rpc_url))
        if not w3.is_connected():  # pragma: no cover - 网络相关
            raise RPCConfigError(
                f"无法连接到 {cfg.name} RPC 节点，请检查 {cfg.rpc_env_var} 或 --rpc-url 配置。"
            )

    # 2) 无任何显式/环境配置时，尝试内置的公共 RPC 列表
    if w3 is None:
        candidates = list(_get_public_rpc_candidates(cfg))
        if not candidates:
            raise RPCConfigError(
                f"未配置 {cfg.name} RPC URL，且当前脚本未内置公共 RPC 列表。"
                f"请通过环境变量 {cfg.rpc_env_var} 或命令行参数 --rpc-url 提供。"
            )

        last_error: Optional[Exception] = None
        for url in candidates:
            candidate_w3 = Web3(Web3.HTTPProvider(url))
            try:
                if candidate_w3.is_connected():  # pragma: no cover - 网络相关
                    w3 = candidate_w3
                    resolved_rpc_url = url
                    break
            except Exception as exc:  # pragma: no cover - 网络相关
                last_error = exc

        if w3 is None:
            urls = ", ".join(candidates)
            extra = f" 最后一次连接错误: {last_error}" if last_error else ""
            raise RPCConfigError(
                f"无法连接到任何 {cfg.name} 公共 RPC 节点。尝试的 URL: {urls}。"  # noqa: E501
                f"请检查本地网络，或通过环境变量 {cfg.rpc_env_var} 或 --rpc-url 指定可用的 RPC。"  # noqa: E501
                + extra
            )

    # Minimal ERC20 ABI: balanceOf, decimals, symbol
    erc20_abi = [
        {
            "name": "decimals",
            "type": "function",
            "stateMutability": "view",
            "inputs": [],
            "outputs": [{"name": "", "type": "uint8"}],
        },
        {
            "name": "symbol",
            "type": "function",
            "stateMutability": "view",
            "inputs": [],
            "outputs": [{"name": "", "type": "string"}],
        },
        {
            "name": "balanceOf",
            "type": "function",
            "stateMutability": "view",
            "inputs": [{"name": "owner", "type": "address"}],
            "outputs": [{"name": "", "type": "uint256"}],
        },
    ]

    contract = w3.eth.contract(address=cfg.usdc_address, abi=erc20_abi)

    try:
        decimals_value = contract.functions.decimals().call()
    except Exception:  # pragma: no cover - 链上行为
        decimals_value = 6

    try:
        symbol_value = contract.functions.symbol().call()
    except Exception:  # pragma: no cover - 链上行为
        symbol_value = "USDC"

    try:
        raw_balance_value = contract.functions.balanceOf(normalized).call()
    except Exception as exc:  # pragma: no cover - 链上行为
        raise RuntimeError(f"调用 balanceOf 失败: {exc}") from exc

    try:
        decimals = int(decimals_value)
    except Exception:
        decimals = 6

    if decimals < 0:
        decimals = 6

    try:
        raw_balance = int(raw_balance_value)
    except Exception:
        # Fallback, though Web3 should already return int-like values.
        raw_balance = 0

    human_balance = raw_balance / (10 ** decimals) if decimals > 0 else float(raw_balance)

    return {
        "address": normalized,
        "network": cfg.name,
        "chain_id": cfg.chain_id,
        "usdc_contract": cfg.usdc_address,
        "symbol": str(symbol_value),
        "decimals": decimals,
        "raw_balance": raw_balance,
        "balance": float(human_balance),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for querying USDC balances.

    Examples
    --------

        python balanece.py 0xYourWallet
        python balanece.py 0xYourWallet --network polygon
        python balanece.py --network polygon  # 使用 .env 中的默认地址
    """

    load_dotenv()

    parser = argparse.ArgumentParser(
        description=(
            "查询指定地址在指定网络上的 USDC ERC20 余额（默认 Polygon / USDC.e）。"
            "在未显式提供 --rpc-url 且未设置对应环境变量时，会自动尝试一小组公共 RPC 节点。"
        )
    )
    parser.add_argument(
        "address",
        nargs="?",
        help=(
            "要查询的 EVM 钱包地址。若省略，则尝试从环境变量 FUNDER_ADDRESS / USER_ADDRESS 中读取。"
        ),
    )
    parser.add_argument(
        "-n",
        "--network",
        dest="network",
        default=os.getenv("USDC_NETWORK", DEFAULT_NETWORK),
        choices=sorted(NETWORKS.keys()),
        help=(
            "查询使用的网络，默认 %(default)s。可选值: "
            + ", ".join(sorted(NETWORKS.keys()))
        ),
    )
    parser.add_argument(
        "--rpc-url",
        dest="rpc_url",
        default=None,
        help=(
            "可选：覆盖默认的 RPC URL。若不提供且未设置对应环境变量，"
            "脚本会自动尝试该网络的一小组公共 RPC 节点。"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出详细结果（方便脚本继续处理）。",
    )

    args = parser.parse_args(argv)

    address = args.address or os.getenv("FUNDER_ADDRESS") or os.getenv("USER_ADDRESS")
    if not address:
        parser.error(
            "未提供钱包地址。请在命令行参数中传入 address，"
            "或在 .env 中设置 FUNDER_ADDRESS / USER_ADDRESS。"
        )

    try:
        result = get_usdc_balance(
            address=address,
            network=args.network,
            rpc_url=args.rpc_url,
        )
    except InvalidAddressError as exc:
        print(f"Invalid address: {exc}")
        return 1
    except RPCConfigError as exc:
        print(f"RPC 配置错误: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"运行时错误: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - 防御性兜底
        print(f"未知错误: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Human-readable output
    symbol = result.get("symbol", "USDC")
    print(f"网络: {result['network']} (chain_id={result['chain_id']})")
    print(f"地址: {result['address']}")
    print(f"USDC 合约: {result['usdc_contract']}")
    print(f"代币符号: {symbol}")
    print(f"原始余额 (raw): {result['raw_balance']}")
    print(
        "折算余额: "
        f"{result['balance']:.6f} {symbol} (decimals={result['decimals']})"
    )

    return 0


if __name__ == "__main__":  # CLI 入口
    import sys

    raise SystemExit(main())

