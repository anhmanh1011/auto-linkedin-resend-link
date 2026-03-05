"""
LoginFlow — LinkedIn Password Reset flow.

Chạy:
    python main.py --flow login
    python main.py --flow login --email hello@emmarcanjo.com
    python main.py --flow login --batch accounts.txt
"""

from base_flow import BaseFlow
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

        # ── Step 0: Activate CAPTCHA solver extension ──
        self.log("Step 0: Setting OmoCaptcha API key...")
        await page.goto(
            "https://omocaptcha.com/set-key/?api_key=OMO_NAIEMPVVKDCZVF64HXQQVM7Z1WKBSZDUHQXWT89FOYO1ANXP5VXNQRYPSXXDD21772698837",
            wait_until="domcontentloaded",
        )
        await self.wait(2, 3)
        await self.screenshot("00_captcha_key_set")

        # ── Step 1: Đi tới LinkedIn ──
        self.log(f"Step 1: Navigating to linkedin.com...")
        await page.goto("https://www.linkedin.com", wait_until="domcontentloaded")
        await self.wait(2, 4)
        await self.screenshot("01_linkedin_home")

        # ── Step 2: Đi tới page request password reset ──
        self.log("Step 2: Navigating to password reset page...")
        await page.goto(
            "https://www.linkedin.com/checkpoint/rp/request-password-reset",
            wait_until="domcontentloaded",
        )
        await self.wait(2, 3)
        await self.screenshot("02_reset_page")

        # ── Step 3: Nhập email vào input #username ──
        self.log(f"Step 3: Typing email: {email}")
        await self.human_type("#username", email)
        await self.wait(1, 2)
        await self.screenshot("03_email_typed")

        # ── Step 4: Click submit ──
        self.log("Step 4: Clicking submit...")
        await self.safe_click("#reset-password-submit-button")
        await self.wait(3, 5)
        await self.screenshot("04_after_submit")

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
        await self.screenshot("05_after_captcha")

        # ── Step 6: Click resend link ──
        self.log("Step 6: Clicking resend link...")
        await self.safe_click("a.challenge-form__footer.resend__link")
        await self.wait(2, 3)
        await self.screenshot("06_after_resend")

        self.log("✅ Password reset request sent!")
        return {"status": "ok", "email": email}
