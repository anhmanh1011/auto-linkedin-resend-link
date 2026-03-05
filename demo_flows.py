"""
Demo: Tạo profile AdsPower + chạy các luồng automation cơ bản.
Sử dụng Playwright kết nối qua CDP (Chrome DevTools Protocol).

Chạy: python demo_flows.py
"""

import asyncio
import logging
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from adspower_client import AdsPowerClient
from config import Config

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")

# ── Screenshot dir ──
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


async def flow_check_ip(page, step: int = 1):
    """Flow 1: Kiểm tra IP hiện tại qua api.ipify.org."""
    logger.info(f"── Flow {step}: Check IP ──")
    await page.goto("https://api.ipify.org?format=json", wait_until="domcontentloaded")
    content = await page.text_content("body")
    logger.info(f"   IP Response: {content}")
    await page.screenshot(path=str(SCREENSHOT_DIR / "01_check_ip.png"))
    logger.info("   📸 Screenshot saved: 01_check_ip.png")
    return content


async def flow_check_fingerprint(page, step: int = 2):
    """Flow 2: Kiểm tra browser fingerprint qua browserleaks."""
    logger.info(f"── Flow {step}: Check Browser Fingerprint ──")
    await page.goto("https://browserleaks.com/canvas", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)  # Chờ page load đầy đủ
    await page.screenshot(path=str(SCREENSHOT_DIR / "02_fingerprint.png"), full_page=True)
    logger.info("   📸 Screenshot saved: 02_fingerprint.png")

    # Lấy User-Agent
    ua = await page.evaluate("navigator.userAgent")
    logger.info(f"   User-Agent: {ua}")

    # Lấy platform
    platform = await page.evaluate("navigator.platform")
    logger.info(f"   Platform: {platform}")

    # Lấy screen size
    screen = await page.evaluate("({w: screen.width, h: screen.height})")
    logger.info(f"   Screen: {screen['w']}x{screen['h']}")


async def flow_google_search(page, query: str = "AdsPower antidetect browser", step: int = 3):
    """Flow 3: Tìm kiếm Google cơ bản."""
    logger.info(f"── Flow {step}: Google Search ──")
    await page.goto("https://www.google.com", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    # Tìm ô search và nhập query
    search_box = page.locator('textarea[name="q"], input[name="q"]')
    await search_box.fill(query)
    await page.wait_for_timeout(1000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "03_google_typing.png"))
    logger.info(f"   Typed: '{query}'")

    # Nhấn Enter
    await search_box.press("Enter")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)

    await page.screenshot(path=str(SCREENSHOT_DIR / "04_google_results.png"))
    logger.info("   📸 Screenshot saved: 04_google_results.png")

    # Đếm kết quả
    results = page.locator("#search .g")
    count = await results.count()
    logger.info(f"   Found ~{count} search results")


async def flow_navigate_multiple_tabs(page, context, step: int = 4):
    """Flow 4: Mở nhiều tab và navigate."""
    logger.info(f"── Flow {step}: Multi-tab Navigation ──")

    urls = [
        ("https://httpbin.org/headers", "Headers"),
        ("https://httpbin.org/ip", "IP Info"),
    ]

    pages = [page]  # Tab đầu tiên đã có sẵn

    for url, name in urls:
        new_page = await context.new_page()
        await new_page.goto(url, wait_until="domcontentloaded")
        await new_page.wait_for_timeout(1500)
        content = await new_page.text_content("body")
        logger.info(f"   Tab [{name}]: {content[:150]}...")
        pages.append(new_page)

    await page.screenshot(path=str(SCREENSHOT_DIR / "05_multi_tab.png"))
    logger.info(f"   📸 Opened {len(pages)} tabs total")

    # Close extra tabs
    for p in pages[1:]:
        await p.close()
    logger.info("   Closed extra tabs")


async def main():
    config = Config.from_env()

    logger.info("🚀 AdsPower Demo — Tạo Profile & Chạy Luồng Cơ Bản")
    logger.info(f"   Target: {config.adspower.base_url}")
    logger.info("")

    async with AdsPowerClient(config.adspower) as client:
        # ── Check AdsPower ──
        if not await client.check_status():
            logger.error("❌ AdsPower không chạy! Hãy mở AdsPower trước.")
            sys.exit(1)

        # ── Tạo profile mới ──
        logger.info("=" * 55)
        logger.info("STEP 1: Tạo Profile Mới")
        logger.info("=" * 55)

        profile_data = await client.create_profile(
            name="demo-automation",
            proxy_config={
                "proxy_type": "noproxy",
                "proxy_soft": "no_proxy",
            },
        )
        profile_id = profile_data["id"]
        logger.info(f"   ✅ Created profile: {profile_id}")

        try:
            # ── Mở browser ──
            logger.info("")
            logger.info("=" * 55)
            logger.info("STEP 2: Mở Browser")
            logger.info("=" * 55)

            browser_data = await client.start_profile(profile_id)
            puppeteer_ws = browser_data["ws"]["puppeteer"]
            logger.info(f"   ✅ Browser opened")
            logger.info(f"   WebSocket: {puppeteer_ws}")

            # Chờ browser khởi động
            await asyncio.sleep(3)

            # ── Kết nối Playwright qua CDP ──
            logger.info("")
            logger.info("=" * 55)
            logger.info("STEP 3: Chạy Các Luồng Automation")
            logger.info("=" * 55)

            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(puppeteer_ws)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                logger.info(f"   ✅ Playwright connected | Pages: {len(context.pages)}")
                logger.info("")

                # ── Chạy các flows ──
                await flow_check_ip(page, step=1)
                logger.info("")

                await flow_check_fingerprint(page, step=2)
                logger.info("")

                await flow_google_search(page, step=3)
                logger.info("")

                await flow_navigate_multiple_tabs(page, context, step=4)
                logger.info("")

                # Disconnect Playwright (không đóng browser)
                # browser.close() sẽ do AdsPower quản lý

        finally:
            # ── Cleanup ──
            logger.info("=" * 55)
            logger.info("STEP 4: Cleanup")
            logger.info("=" * 55)

            await asyncio.sleep(2)
            await client.stop_profile(profile_id)
            logger.info(f"   ✅ Browser closed")

            await asyncio.sleep(1)
            await client.delete_profile([profile_id])
            logger.info(f"   ✅ Profile deleted: {profile_id}")

    logger.info("")
    logger.info("=" * 55)
    logger.info("🎉 Demo hoàn tất! Screenshots saved in ./screenshots/")
    logger.info("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
