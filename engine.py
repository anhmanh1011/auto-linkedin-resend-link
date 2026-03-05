"""
FlowRunner — Engine xử lý mọi thứ ngoài logic flow.

Tạo profile → Mở browser → Kết nối Playwright → Chạy flow → Cleanup.
User không cần quan tâm file này, chỉ cần viết Flow class.
"""

import asyncio
import logging
import random
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from playwright.async_api import async_playwright

from adspower_client import AdsPowerClient, AdsPowerError
from base_flow import BaseFlow
from config import Config

logger = logging.getLogger("engine")


@dataclass
class FlowResult:
    """Kết quả chạy 1 flow."""
    success: bool = False
    profile_id: str = ""
    account: dict = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0


class FlowRunner:
    """
    Engine chạy automation flows.

    Handles:
        - Profile management (tạo / reuse)
        - Browser lifecycle (mở / đóng)
        - Playwright connection (CDP)
        - Flow execution với retry
        - Chạy batch nhiều accounts
        - Cleanup
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self._client: Optional[AdsPowerClient] = None

    async def _get_client(self) -> AdsPowerClient:
        if not self._client:
            self._client = AdsPowerClient(self.config.adspower)
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ──────────────────────────────────────────────
    # Core: Run 1 flow cho 1 account
    # ──────────────────────────────────────────────

    async def run_flow(
        self,
        flow: BaseFlow,
        keep_profile: bool = False,
        headless: bool = False,
    ) -> FlowResult:
        """
        Chạy 1 flow instance.

        Args:
            flow:          Flow instance (đã có account data)
            keep_profile:  True = giữ profile sau khi chạy xong
            headless:      True = chạy headless mode

        Returns:
            FlowResult
        """
        client = await self._get_client()
        result = FlowResult(account=flow.account)
        profile_id = ""
        max_retries = self.config.engine.max_retries

        # ── Check AdsPower ──
        if not await client.check_status():
            result.error = "AdsPower is not running"
            logger.error("❌ AdsPower is not running!")
            return result

        try:
            # ── Tạo profile ──
            logger.info(f"[{flow.flow_name}] Creating profile...")
            profile_data = await client.create_profile(
                name=f"{flow.flow_name}-auto",
                proxy_config={
                    "proxy_type": "noproxy",
                    "proxy_soft": "no_proxy",
                },
                fingerprint_config={
                    "automatic_timezone": "1",
                    "language": ["en-US", "en"],
                    "flash": "block",
                    "webrtc": "disabled",
                    "random_ua": {
                        "ua_system_version": [
                            "Windows 10", "Windows 11",
                            "Mac OS X 13", "Mac OS X 14",
                        ],
                    },
                },
            )
            profile_id = profile_data["id"]
            flow.profile_id = profile_id
            result.profile_id = profile_id
            logger.info(f"[{flow.flow_name}] Profile created: {profile_id}")

            # ── Mở browser ──
            logger.info(f"[{flow.flow_name}] Starting browser...")
            browser_data = await client.start_profile(
                profile_id, headless=headless
            )
            puppeteer_ws = browser_data["ws"]["puppeteer"]
            logger.info(f"[{flow.flow_name}] Browser started (port={browser_data.get('debug_port', 'N/A')})")

            # Chờ browser khởi động
            await asyncio.sleep(3)

            # ── Kết nối Playwright ──
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(puppeteer_ws)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                # Inject vào flow
                flow.page = page
                flow.context = context

                logger.info(f"[{flow.flow_name}] Playwright connected")

                # ── Chạy flow với retry ──
                for attempt in range(1, max_retries + 1):
                    result.attempts = attempt
                    try:
                        logger.info(f"[{flow.flow_name}] Running... (attempt {attempt}/{max_retries})")

                        # Lifecycle: setup → run → teardown
                        await flow.setup(page)
                        flow_result = await flow.run(page)
                        await flow.teardown(page)

                        result.success = True
                        result.result = flow_result
                        logger.info(f"[{flow.flow_name}] ✅ Success!")
                        break

                    except Exception as e:
                        logger.warning(
                            f"[{flow.flow_name}] ⚠️ Attempt {attempt} failed: {e}"
                        )
                        await flow.on_error(e, page)

                        if attempt < max_retries:
                            delay = random.uniform(
                                self.config.engine.task_delay_min,
                                self.config.engine.task_delay_max,
                            )
                            logger.info(f"[{flow.flow_name}] Retrying in {delay:.1f}s...")
                            await asyncio.sleep(delay)
                        else:
                            result.error = str(e)
                            logger.error(
                                f"[{flow.flow_name}] ❌ Failed after {max_retries} attempts"
                            )

        except Exception as e:
            result.error = str(e)
            logger.error(f"[{flow.flow_name}] ❌ Engine error: {e}")
            traceback.print_exc()

        finally:
            # ── Cleanup ──
            if profile_id:
                try:
                    await asyncio.sleep(2)
                    await client.stop_profile(profile_id)
                    logger.info(f"[{flow.flow_name}] Browser closed")

                    if not keep_profile:
                        await asyncio.sleep(1)
                        await client.delete_profile([profile_id])
                        logger.info(f"[{flow.flow_name}] Profile deleted: {profile_id}")
                    else:
                        logger.info(f"[{flow.flow_name}] Profile kept: {profile_id}")
                except Exception as e:
                    logger.warning(f"[{flow.flow_name}] Cleanup warning: {e}")

        return result

    # ──────────────────────────────────────────────
    # Batch: Chạy nhiều accounts
    # ──────────────────────────────────────────────

    async def run_batch(
        self,
        flow_class: Type[BaseFlow],
        accounts: list[dict[str, Any]],
        keep_profiles: bool = False,
        headless: bool = False,
    ) -> list[FlowResult]:
        """
        Chạy flow cho nhiều accounts (song song, giới hạn bởi max_workers).

        Args:
            flow_class:    Class flow (không phải instance)
            accounts:      Danh sách account dicts
            keep_profiles: Giữ profiles sau khi chạy
            headless:      Chạy headless mode

        Returns:
            List[FlowResult]

        Example:
            accounts = [
                {"email": "user1@mail.com", "password": "pass1"},
                {"email": "user2@mail.com", "password": "pass2"},
            ]
            results = await runner.run_batch(LoginFlow, accounts)
        """
        max_workers = self.config.engine.max_workers
        semaphore = asyncio.Semaphore(max_workers)
        results: list[FlowResult] = []

        logger.info(
            f"Starting batch: {len(accounts)} accounts, "
            f"max_workers={max_workers}, flow={flow_class.flow_name}"
        )

        async def _run_one(account: dict, index: int):
            async with semaphore:
                # Random delay giữa các task
                if index > 0:
                    delay = random.uniform(
                        self.config.engine.task_delay_min,
                        self.config.engine.task_delay_max,
                    )
                    await asyncio.sleep(delay)

                flow = flow_class(account=account)
                logger.info(f"[Batch {index + 1}/{len(accounts)}] Starting...")
                result = await self.run_flow(
                    flow,
                    keep_profile=keep_profiles,
                    headless=headless,
                )
                results.append(result)
                status = "✅" if result.success else "❌"
                logger.info(
                    f"[Batch {index + 1}/{len(accounts)}] {status} "
                    f"({result.attempts} attempts)"
                )

        tasks = [_run_one(acc, i) for i, acc in enumerate(accounts)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Summary
        success = sum(1 for r in results if r.success)
        logger.info(
            f"Batch complete: {success}/{len(accounts)} success"
        )

        return results
