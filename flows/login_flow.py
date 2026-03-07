"""
LoginFlow — LinkedIn Password Reset flow.

1 profile check tối đa 5 emails:
  Step 0-1: Setup 1 lần (OmoCaptcha + LinkedIn)
  Step 2-7: Loop — bốc 1 email từ queue mỗi lần
"""

import asyncio
import os

from base_flow import BaseFlow
from config import config
from engine import SkipEmailError
from playwright.async_api import Page

# Số email tối đa mỗi profile
EMAILS_PER_PROFILE = 5


class LoginFlow(BaseFlow):
    """
    Flow request password reset trên LinkedIn.

    Account dict cần có:
        - email_queue: asyncio.Queue[str]   (shared queue)
        hoặc
        - email: str  (single email, backward compat)
    """

    flow_name = "login"

    async def run(self, page: Page):
        email_queue = self.account.get("email_queue", None)
        captcha_key = config.captcha.omocaptcha_api_key
        results = []

        # Backward compat: single email mode
        if email_queue is None:
            single = self.account.get("email", "")
            if not single:
                self.log("   ⚠️ No email provided")
                return {"status": "error", "results": []}
            # Tạo queue tạm với 1 email
            email_queue = asyncio.Queue()
            await email_queue.put(single)

        # ══════════════════════════════════════
        # Step 0: Set OmoCaptcha key (1 lần)
        # ══════════════════════════════════════
        if captcha_key:
            self.log("Step 0: Setting OmoCaptcha API key...")
            set_key_url = f"https://omocaptcha.com/set-key/?api_key={captcha_key}"
            try:
                await page.goto(
                    set_key_url,
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                self.log("   ✅ OmoCaptcha key set")
            except Exception as e:
                self.log(f"   ⚠️ OmoCaptcha set-key failed: {e.__class__.__name__}")
                self.log("   ↪ Continuing — extension may already be configured")
            await self.wait(1, 2)

        # ══════════════════════════════════════
        # Step 1: Đi tới LinkedIn (detect proxy)
        # ══════════════════════════════════════
        self.log("Step 1: Navigating to linkedin.com...")
        try:
            await page.goto(
                "https://www.linkedin.com",
                wait_until="domcontentloaded",
                timeout=15000,
            )
        except Exception as e:
            raise SkipEmailError(f"Proxy dead — cannot reach linkedin.com: {e.__class__.__name__}")
        await self.wait(2, 4)

        # ══════════════════════════════════════
        # Loop: Steps 2-7 — bốc email từ queue
        # ══════════════════════════════════════
        for round_num in range(EMAILS_PER_PROFILE):
            # ── Bốc 1 email từ queue ──
            try:
                email = email_queue.get_nowait()
            except asyncio.QueueEmpty:
                self.log(f"   📭 Queue empty — no more emails")
                break

            email_label = f"[#{round_num + 1}]"
            self.log(f"\n{'─' * 40}")
            self.log(f"📧 {email_label} Processing: {email}")
            self.log(f"{'─' * 40}")

            try:
                # ── Step 2: Đi tới password reset page ──
                self.log(f"{email_label} Step 2: Navigating to password reset page...")
                await page.goto(
                    "https://www.linkedin.com/checkpoint/rp/request-password-reset",
                    wait_until="domcontentloaded",
                )
                await self.wait(2, 3)

                # ── Step 3: Nhập email ──
                self.log(f"{email_label} Step 3: Typing email: {email}")
                await self.human_type("#username", email)
                await self.wait(1, 2)

                # ── Step 4: Click submit ──
                self.log(f"{email_label} Step 4: Clicking submit...")
                await self.safe_click("#reset-password-submit-button")
                await self.wait(3, 5)

                # ── Step 5: Chờ CAPTCHA ──
                self.log(f"{email_label} Step 5: Waiting for CAPTCHA...")
                try:
                    await page.wait_for_selector(
                        "a.challenge-form__footer.resend__link",
                        state="visible",
                        timeout=120000,
                    )
                    self.log(f"{email_label}    ✅ CAPTCHA solved!")
                except Exception:
                    self.log(f"{email_label}    ⚠️ CAPTCHA timeout — skipping this email")
                    with open("failed.txt", "a") as f:
                        f.write(f"{email}\n")
                    results.append({"status": "captcha_timeout", "email": email})
                    continue  # Bốc email tiếp

                await self.wait(2, 3)

                # ── Step 6: Click resend link ──
                self.log(f"{email_label} Step 6: Clicking resend link...")
                await self.safe_click("a.challenge-form__footer.resend__link")
                await self.wait(3, 5)

                # ── Step 7: Check kết quả ──
                current_url = page.url
                self.log(f"{email_label} Step 7: Checking result URL: {current_url}")

                if current_url.startswith("https://www.linkedin.com/checkpoint/rp/id-verify-create"):
                    self.log(f"{email_label}    ✅ SUCCESS — {email}")
                    with open("success.txt", "a") as f:
                        f.write(f"{email}\n")
                    results.append({"status": "success", "email": email})
                else:
                    self.log(f"{email_label}    ❌ FAILED — {email} (url={current_url[:80]})")
                    with open("failed.txt", "a") as f:
                        f.write(f"{email}\n")
                    results.append({"status": "failed", "email": email, "url": current_url})

            except Exception as e:
                self.log(f"{email_label}    ❌ Error: {e.__class__.__name__}: {e}")
                with open("failed.txt", "a") as f:
                    f.write(f"{email}\n")
                results.append({"status": "error", "email": email, "error": str(e)})

        # ── Summary ──
        success_count = sum(1 for r in results if r["status"] == "success")
        self.log(f"\n📊 Profile done: {success_count}/{len(results)} success")
        return {"status": "batch_done", "results": results, "total": len(results), "success": success_count}
