"""
Main entry point — chạy automation flow.

Usage:
    python main.py              # Đọc emails.txt, nhập số luồng
    python main.py --keep       # Giữ profile sau khi chạy
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from engine import FlowRunner
from flows.login_flow import LoginFlow

# ── Logging (console + file) ──
os.makedirs("logs", exist_ok=True)
log_file = f"logs/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

log_format = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),                         # Console
        logging.FileHandler(log_file, encoding="utf-8"), # File
    ],
)
logger = logging.getLogger("main")
logger.info(f"📝 Log file: {log_file}")

EMAIL_FILE = "emails.txt"


def load_emails(file_path: str) -> list[dict]:
    """Load emails từ file. Mỗi dòng 1 email."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    accounts = []
    with open(file_path, "r") as f:
        for line in f:
            email = line.strip()
            if email and not email.startswith("#"):
                accounts.append({"email": email})
    return accounts


async def run(workers: int, keep: bool):
    # ── Load emails ──
    accounts = load_emails(EMAIL_FILE)
    if not accounts:
        logger.error(f"No emails found in {EMAIL_FILE}")
        return

    logger.info("=" * 55)
    logger.info("🚀 Automation Framework — LinkedIn Password Reset")
    logger.info(f"   Emails: {len(accounts)} | Workers: {workers}")
    logger.info("=" * 55)

    async with FlowRunner() as runner:
        results = await runner.run_batch(
            LoginFlow,
            accounts,
            max_workers=workers,
            keep_profiles=keep,
        )

        # ── Summary ──
        logger.info("")
        logger.info("=" * 55)
        logger.info("📊 RESULTS")
        logger.info("=" * 55)
        total_success = 0
        total_emails = 0
        for i, r in enumerate(results, 1):
            if r.result and isinstance(r.result, dict):
                batch_res = r.result.get("results", [])
                for br in batch_res:
                    total_emails += 1
                    status = "✅" if br.get("status") == "success" else "❌"
                    logger.info(f"  {status} {br.get('email', 'N/A')} → {br.get('status', '?')}")
                    if br.get("status") == "success":
                        total_success += 1
            else:
                total_emails += 1
                logger.info(f"  ❌ Group {i}: {r.error or 'unknown error'}")

        logger.info(f"\n  Total: {total_success}/{total_emails} success")

    logger.info("Done.")


def main():
    # ── Load và hiển thị emails ──
    accounts = load_emails(EMAIL_FILE)
    print(f"\n📧 Loaded {len(accounts)} emails from {EMAIL_FILE}")
    print(f"   First: {accounts[0]['email']}" if accounts else "   (empty)")
    print(f"   Last:  {accounts[-1]['email']}" if len(accounts) > 1 else "")

    # ── Đọc số proxy keys ──
    proxy_keys = []
    try:
        with open("proxy.txt", "r") as f:
            proxy_keys = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        pass

    if proxy_keys:
        max_allowed = len(proxy_keys)
        print(f"\n🔑 KiotProxy: {max_allowed} keys loaded → max {max_allowed} workers")
    else:
        max_allowed = len(accounts)
        print("\n⚠️  No proxy keys found (proxy.txt) → running without proxy")

    # ── Nhập số luồng ──
    while True:
        try:
            workers = int(input(f"\n🔢 Nhập số luồng (1-{max_allowed}): "))
            if 1 <= workers <= max_allowed:
                break
            print(f"   ⚠️ Nhập từ 1 đến {max_allowed}")
        except ValueError:
            print("   ⚠️ Nhập số!")

    print(f"\n▶️  Starting {len(accounts)} emails × {workers} workers...\n")
    asyncio.run(run(workers, keep=False))


if __name__ == "__main__":
    main()
