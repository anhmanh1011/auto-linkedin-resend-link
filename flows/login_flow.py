"""
LoginFlow — LinkedIn Password Reset flow.

Chạy:
    python main.py --flow login
    python main.py --flow login --email hello@emmarcanjo.com
    python main.py --flow login --batch accounts.txt
"""

from base_flow import BaseFlow
from config import config
from playwright.async_api import Page


class LoginFlow(BaseFlow):
    """
    Flow request password reset trên LinkedIn.

    Account dict cần có:
        - email: str (LinkedIn email)
    """

    flow_name = "login"

    async def run(self, page: Page):
        email = self.account.get("email", "hello@emmarcanjo.com")
        captcha_key = config.captcha.omocaptcha_api_key

        # ── Step 0: Activate CAPTCHA solver extension ──
        if captcha_key:
            self.log("Step 0: Setting OmoCaptcha API key...")
            try:
                await page.goto(
                    f"https://omocaptcha.com/set-key/?api_key={captcha_key}",
                    wait_until="domcontentloaded",
                    timeout=10000,
                )
                self.log("   ✅ OmoCaptcha key set")
            except Exception as e:
                self.log(f"   ⚠️ OmoCaptcha set-key failed (proxy block?): {e.__class__.__name__}")
                self.log("   ↪ Retrying via direct JS injection...")
                try:
                    await page.evaluate(
                        f"window.open('https://omocaptcha.com/set-key/?api_key={captcha_key}', '_blank')"
                    )
                    await self.wait(2, 3)
                    # Close the extra tab
                    pages = page.context.pages
                    if len(pages) > 1:
                        await pages[-1].close()
                except Exception:
                    self.log("   ⚠️ Skipping OmoCaptcha — extension may already be active")
            await self.wait(1, 2)

        # ── Step 1: Đi tới LinkedIn ──
        self.log(f"Step 1: Navigating to linkedin.com...")
        await page.goto("https://www.linkedin.com", wait_until="domcontentloaded")
        await self.wait(2, 4)

        # ── Step 2: Đi tới page request password reset ──
        self.log("Step 2: Navigating to password reset page...")
        await page.goto(
            "https://www.linkedin.com/checkpoint/rp/request-password-reset",
            wait_until="domcontentloaded",
        )
        await self.wait(2, 3)

        # ── Step 3: Nhập email vào input #username ──
        self.log(f"Step 3: Typing email: {email}")
        await self.human_type("#username", email)
        await self.wait(1, 2)

        # ── Step 4: Click submit ──
        self.log("Step 4: Clicking submit...")
        await self.safe_click("#reset-password-submit-button")
        await self.wait(3, 5)

        # ── Step 5: Chờ extension giải reCAPTCHA ──
        self.log("Step 5: Waiting for CAPTCHA extension to solve...")
        # Chờ resend link xuất hiện (chỉ hiện sau khi CAPTCHA pass)
        try:
            await page.wait_for_selector(
                "a.challenge-form__footer.resend__link",
                state="visible",
                timeout=120000,  # Max 120s
            )
            self.log("   ✅ CAPTCHA solved!")
        except Exception:
            self.log("   ⚠️ CAPTCHA timeout after 120s")

        await self.wait(2, 3)

        # ── Step 6: Click resend link ──
        self.log("Step 6: Clicking resend link...")
        await self.safe_click("a.challenge-form__footer.resend__link")
        await self.wait(3, 5)

        # ── Step 7: Check kết quả ──
        current_url = page.url
        self.log(f"Step 7: Checking result URL: {current_url}")

        if current_url.startswith("https://www.linkedin.com/checkpoint/rp/id-verify-create"):
            self.log(f"   ✅ SUCCESS — {email}")
            with open("success.txt", "a") as f:
                f.write(f"{email}\n")
            return {"status": "success", "email": email}
        else:
            self.log(f"   ❌ FAILED — {email} (url={current_url[:80]})")
            with open("failed.txt", "a") as f:
                f.write(f"{email}\n")
            return {"status": "failed", "email": email, "url": current_url}
