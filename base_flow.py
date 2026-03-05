"""
BaseFlow — Abstract base class cho mọi automation flow.

User chỉ cần kế thừa class này và override method `run()`.
Base framework lo hết phần còn lại (profile, browser, Playwright, cleanup).

Example:
    class LoginFlow(BaseFlow):
        flow_name = "login"

        async def run(self, page):
            await page.goto("https://example.com/login")
            await page.fill("#email", self.account["email"])
            await page.fill("#password", self.account["password"])
            await page.click("#submit")
            await self.screenshot("after_login")
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import Page, BrowserContext


class BaseFlow(ABC):
    """
    Abstract base class cho automation flows.

    Attributes:
        flow_name:    Tên flow (dùng cho logging & screenshots)
        account:      Dict chứa account data (email, password, etc.)
        profile_id:   AdsPower profile ID (set by engine)
        page:         Playwright Page (set by engine)
        context:      Playwright BrowserContext (set by engine)
    """

    # ── Override ở subclass ──
    flow_name: str = "base"

    def __init__(self, account: Optional[dict[str, Any]] = None):
        self.account: dict[str, Any] = account or {}
        self.profile_id: str = ""
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
        self.logger = logging.getLogger(f"flow.{self.flow_name}")
        self._screenshot_dir = Path("screenshots")

    # ──────────────────────────────────────────────
    # User PHẢI override
    # ──────────────────────────────────────────────

    @abstractmethod
    async def run(self, page: Page) -> Any:
        """
        Logic automation chính — USER VIẾT CODE Ở ĐÂY.

        Args:
            page: Playwright Page, đã sẵn sàng dùng.

        Returns:
            Bất kỳ result nào (hoặc None).

        Example:
            async def run(self, page):
                await page.goto("https://example.com")
                await page.fill("#email", self.account["email"])
                await page.click("#submit")
                return {"status": "ok"}
        """
        pass

    # ──────────────────────────────────────────────
    # User CÓ THỂ override (optional hooks)
    # ──────────────────────────────────────────────

    async def setup(self, page: Page):
        """Hook chạy TRƯỚC run(). Override nếu cần setup."""
        pass

    async def teardown(self, page: Page):
        """Hook chạy SAU run(). Override nếu cần cleanup."""
        pass

    async def on_error(self, error: Exception, page: Page):
        """
        Hook khi run() gặp lỗi. Override để xử lý custom.
        Mặc định: chụp screenshot lỗi.
        """
        await self.screenshot("error")
        self.logger.error(f"Flow error: {error}")

    # ──────────────────────────────────────────────
    # Helper methods (dùng trong run())
    # ──────────────────────────────────────────────

    async def screenshot(self, name: str, full_page: bool = False):
        """
        Chụp screenshot và lưu vào thư mục screenshots.

        Args:
            name: Tên file (không cần extension)
            full_page: Chụp toàn bộ page (scroll)
        """
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self.flow_name}_{self.profile_id}_{name}.png"
        path = self._screenshot_dir / filename
        if self.page:
            await self.page.screenshot(path=str(path), full_page=full_page)
            self.logger.info(f"📸 Screenshot: {filename}")
        return str(path)

    async def wait(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Random delay giống người thật."""
        delay = random.uniform(min_sec, max_sec)
        self.logger.debug(f"Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)

    async def human_type(self, selector: str, text: str, delay: int = 80):
        """Gõ text từng ký tự giống người thật."""
        if self.page:
            locator = self.page.locator(selector)
            await locator.click()
            await locator.fill("")  # Clear trước
            await locator.type(text, delay=delay)

    async def safe_click(self, selector: str, timeout: float = 10000):
        """Click element, chờ nó xuất hiện trước."""
        if self.page:
            await self.page.wait_for_selector(selector, timeout=timeout)
            await self.page.click(selector)

    async def wait_for_navigation(self, url_pattern: str = "", timeout: float = 30000):
        """Chờ navigate đến URL chứa pattern."""
        if self.page:
            if url_pattern:
                await self.page.wait_for_url(f"**{url_pattern}**", timeout=timeout)
            else:
                await self.page.wait_for_load_state("domcontentloaded")

    def log(self, msg: str):
        """Log message tiện dụng."""
        self.logger.info(msg)

    def __repr__(self):
        return f"<{self.__class__.__name__} flow={self.flow_name} profile={self.profile_id}>"
