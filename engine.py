"""
FlowRunner — Engine xử lý mọi thứ ngoài logic flow.

Tạo profile → Mở browser → Kết nối Playwright → Chạy flow → Cleanup.
User không cần quan tâm file này, chỉ cần viết Flow class.
"""

import asyncio
import logging
import math
import random
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from playwright.async_api import async_playwright

from adspower_client import AdsPowerClient, AdsPowerError
from base_flow import BaseFlow
from config import Config
from kiotproxy_client import KiotProxyClient

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
        - KiotProxy integration (1 key = 1 worker)
        - Cleanup
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self._client: Optional[AdsPowerClient] = None
        self._kiot_client: Optional[KiotProxyClient] = None
        self._proxy_keys: list[str] = []
        self._load_proxy_keys()

    def _load_proxy_keys(self):
        """Load KiotProxy API keys từ proxy.txt. Mỗi dòng 1 key."""
        proxy_file = self.config.proxy.proxy_file
        try:
            with open(proxy_file, "r") as f:
                for line in f:
                    key = line.strip()
                    if key and not key.startswith("#"):
                        self._proxy_keys.append(key)
            if self._proxy_keys:
                logger.info(f"Loaded {len(self._proxy_keys)} KiotProxy keys from {proxy_file}")
            else:
                logger.info("No proxy keys loaded — running without proxy")
        except FileNotFoundError:
            logger.info(f"Proxy file not found ({proxy_file}) — running without proxy")

    async def _get_kiot_client(self) -> KiotProxyClient:
        if not self._kiot_client:
            self._kiot_client = KiotProxyClient()
        return self._kiot_client

    async def _get_proxy_for_worker(self, worker_index: int) -> Optional[dict]:
        """Lấy proxy từ KiotProxy API cho worker cụ thể."""
        if not self._proxy_keys:
            return None
        key = self._proxy_keys[worker_index % len(self._proxy_keys)]
        kiot = await self._get_kiot_client()
        proxy = await kiot.get_new_proxy(key)
        return proxy

    async def _get_client(self) -> AdsPowerClient:
        if not self._client:
            self._client = AdsPowerClient(self.config.adspower)
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
        if self._kiot_client:
            await self._kiot_client.close()
            self._kiot_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ──────────────────────────────────────────────
    # Window tiling
    # ──────────────────────────────────────────────

    @staticmethod
    def _get_screen_size() -> tuple[int, int]:
        """Lấy screen resolution. Mặc định 1920x1080 nếu không detect được."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080

    async def _tile_window(
        self, page, worker_index: int, total_workers: int
    ):
        """Đẩy cửa sổ browser ra ngoài màn hình để không làm phiền user."""
        try:
            # Override Page Visibility API — để page luôn nghĩ nó đang visible
            await page.evaluate("""() => {
                Object.defineProperty(document, 'hidden', { get: () => false });
                Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
                document.addEventListener('visibilitychange', e => {
                    e.stopImmediatePropagation();
                }, true);
            }""")

            # Đẩy window ra ngoài màn hình (vẫn "visible" với browser)
            cdp = await page.context.new_cdp_session(page)
            window = await cdp.send("Browser.getWindowForTarget")
            window_id = window["windowId"]
            await cdp.send("Browser.setWindowBounds", {
                "windowId": window_id,
                "bounds": {
                    "left": -3000,
                    "top": -3000,
                    "width": 1024,
                    "height": 768,
                    "windowState": "normal",
                },
            })
            await cdp.detach()
            logger.info(f"[{worker_index}] Window moved off-screen")
        except Exception as e:
            logger.warning(f"Window move failed: {e}")

    # ──────────────────────────────────────────────
    # Core: Run 1 flow cho 1 account
    # ──────────────────────────────────────────────

    async def run_flow(
        self,
        flow: BaseFlow,
        keep_profile: bool = False,
        headless: bool = False,
        worker_index: int = 0,
        total_workers: int = 1,
    ) -> FlowResult:
        """
        Chạy 1 flow instance.

        Args:
            flow:          Flow instance (đã có account data)
            keep_profile:  True = giữ profile sau khi chạy xong
            headless:      True = chạy headless mode
            worker_index:  Index của worker (dùng để chọn proxy key)

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
            # ── Proxy via KiotProxy API ──
            proxy = await self._get_proxy_for_worker(worker_index)
            if proxy:
                proxy_config = {
                    "proxy_type": "http",
                    "proxy_host": proxy["host"],
                    "proxy_port": proxy["port"],
                    "proxy_user": proxy.get("user", ""),
                    "proxy_password": proxy.get("pass", ""),
                    "proxy_soft": "other",
                }
                logger.info(f"[{flow.flow_name}] Using proxy: {proxy['host']}:{proxy['port']}")
            else:
                proxy_config = {
                    "proxy_type": "noproxy",
                    "proxy_soft": "no_proxy",
                }

            # ── Tạo profile ──
            logger.info(f"[{flow.flow_name}] Creating profile...")
            profile_data = await client.create_profile(
                name=f"{flow.flow_name}-auto",
                proxy_config=proxy_config,
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
        max_workers: int = 0,
        keep_profiles: bool = False,
        headless: bool = False,
    ) -> list[FlowResult]:
        """
        Chạy flow cho nhiều accounts (song song, giới hạn bởi max_workers).

        Args:
            flow_class:    Class flow (không phải instance)
            accounts:      Danh sách account dicts
            max_workers:   Số luồng song song (0 = dùng config)
            keep_profiles: Giữ profiles sau khi chạy
            headless:      Chạy headless mode

        Returns:
            List[FlowResult]
        """
        workers = max_workers if max_workers > 0 else self.config.engine.max_workers
        semaphore = asyncio.Semaphore(workers)
        results: list[FlowResult] = []

        logger.info(
            f"Starting batch: {len(accounts)} accounts, "
            f"max_workers={workers}, flow={flow_class.flow_name}"
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
                    worker_index=index % workers,
                    total_workers=workers,
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
