"""轻量级入口脚本：调用 claiming.claim_all_winnings 并打印 JSON 结果。

支持命令行用法，例如：

    python3.12 polytools/claim.py --user-address 0x... --execute

默认启用 dry-run（不发真实交易），可通过 --execute 切换为执行模式。
"""

from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv

from claiming import claim_all_winnings


def main() -> None:
    """CLI 入口：解析参数并调用 claim_all_winnings。"""

    load_dotenv()

    parser = argparse.ArgumentParser(
        description=(
            "一键 Claim 所有可领取盈利（默认 dry-run，只展示将要领取的明细和总金额）。"
        )
    )
    parser.add_argument(
        "--user-address",
        "--address",
        dest="user_address",
        default=os.getenv("FUNDER_ADDRESS") or os.getenv("USER_ADDRESS"),
        help=(
            "要查询和领取的地址，默认从环境变量 FUNDER_ADDRESS 或 USER_ADDRESS 读取。"
        ),
    )
    parser.add_argument(
        "--private-key",
        dest="private_key",
        default=os.getenv("PRIVATE_KEY"),
        help="用于签名的私钥，默认从环境变量 PRIVATE_KEY 读取。",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际发起 gasless / 链上 Claim，而不仅仅是 dry-run。",
    )
    parser.add_argument(
        "--fallback-rpc-url",
        dest="fallback_rpc_url",
        default=os.getenv("POLYGON_RPC_URL"),
        help="可选：链上回退模式使用的 Polygon RPC URL。",
    )
    parser.add_argument(
        "--max-gas-price-gwei",
        dest="max_gas_price_gwei",
        type=int,
        default=None,
        help="可选：仅在链上回退模式下生效的单笔 gas 价格上限（gwei）。",
    )
    parser.add_argument(
        "--builder-api-key",
        dest="builder_api_key",
        default=os.getenv("POLY_BUILDER_API_KEY"),
        help=(
            "可选：Builder API Key，若提供则覆盖环境变量 POLY_BUILDER_API_KEY。"
        ),
    )
    parser.add_argument(
        "--builder-secret",
        dest="builder_secret",
        default=os.getenv("POLY_BUILDER_SECRET"),
        help=(
            "可选：Builder Secret，若提供则覆盖环境变量 POLY_BUILDER_SECRET。"
        ),
    )
    parser.add_argument(
        "--builder-passphrase",
        dest="builder_passphrase",
        default=os.getenv("POLY_BUILDER_PASSPHRASE"),
        help=(
            "可选：Builder Passphrase，若提供则覆盖环境变量 POLY_BUILDER_PASSPHRASE。"
        ),
    )

    args = parser.parse_args()

    if not args.user_address:
        parser.error(
            "必须通过 --user-address 或环境变量 FUNDER_ADDRESS / USER_ADDRESS 指定地址。"
        )
    if not args.private_key:
        parser.error(
            "必须通过 --private-key 或环境变量 PRIVATE_KEY 提供私钥。"
        )

    # CLI 显式传入的 Builder 凭证优先于环境变量。
    if args.builder_api_key:
        os.environ["POLY_BUILDER_API_KEY"] = args.builder_api_key
    if args.builder_secret:
        os.environ["POLY_BUILDER_SECRET"] = args.builder_secret
    if args.builder_passphrase:
        os.environ["POLY_BUILDER_PASSPHRASE"] = args.builder_passphrase

    result = claim_all_winnings(
        private_key=args.private_key,
        user_address=args.user_address,
        dry_run=not args.execute,
        fallback_rpc_url=args.fallback_rpc_url,
        max_gas_price_gwei=args.max_gas_price_gwei,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

