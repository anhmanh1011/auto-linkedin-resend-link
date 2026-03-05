"""
Main entry point — chạy automation flow.

Usage:
    python main.py                              # Chạy mặc định
    python main.py --batch accounts.txt         # Chạy nhiều accounts
    python main.py --keep                       # Giữ profile sau khi chạy
"""

import argparse
import asyncio
import logging
import sys

from engine import FlowRunner
from flows.login_flow import LoginFlow

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def load_accounts(file_path: str) -> list[dict]:
    """Load accounts từ file. Format: email|password per line."""
    accounts = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                accounts.append({"email": parts[0], "password": parts[1]})
            elif len(parts) == 1:
                accounts.append({"email": parts[0]})
            else:
                logger.warning(f"Skipping invalid line: {line}")
    return accounts


async def run(args):
    logger.info("=" * 55)
    logger.info("🚀 Automation Framework")
    logger.info("=" * 55)

    async with FlowRunner() as runner:
        if args.batch:
            accounts = load_accounts(args.batch)
            if not accounts:
                logger.error(f"No accounts found in {args.batch}")
                return
            logger.info(f"Loaded {len(accounts)} accounts from {args.batch}")
            results = await runner.run_batch(
                LoginFlow, accounts,
                keep_profiles=args.keep,
            )
            success = sum(1 for r in results if r.success)
            logger.info(f"\nTotal: {success}/{len(results)} success")
        else:
            flow = LoginFlow()
            result = await runner.run_flow(flow, keep_profile=args.keep)
            if result.success:
                logger.info(f"✅ Done! Result: {result.result}")
            else:
                logger.error(f"❌ Failed: {result.error}")

    logger.info("Done.")


def main():
    parser = argparse.ArgumentParser(description="Automation Framework")
    parser.add_argument("--batch", help="Path to accounts file (email|password per line)")
    parser.add_argument("--keep", action="store_true", help="Keep profile after run")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
