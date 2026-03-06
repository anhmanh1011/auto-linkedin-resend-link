"""
LoginFlow — LinkedIn Password Reset flow.

Chạy:
    python main.py --flow login
    python main.py --flow login --email hello@emmarcanjo.com
    python main.py --flow login --batch accounts.txt
"""

import json
import os
from pathlib import Path

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

    @staticmethod
    def _find_and_patch_omocaptcha_config(adspower_root: str, api_key: str) -> str:
        """
        Tìm configs.json của OmoCaptcha extension trong thư mục AdsPower global
        và đảm bảo api_key được set đúng.

        Returns: 'patched', 'already_set', hoặc 'not_found'
        """
        root = Path(adspower_root)
        search_paths = [
            root / "extension",
            root / "ext_env",
        ]

        found = False
        for search_root in search_paths:
            if not search_root.exists():
                continue
            for configs_file in search_root.rglob("configs.json"):
                try:
                    content = configs_file.read_text(encoding="utf-8")
                    data = json.loads(content)
                    if "api_key" not in data:
                        continue
                    found = True
                    current_key = data.get("api_key", "")
                    if current_key == api_key:
                        continue  # Đã đúng rồi
                    # Cập nhật api_key
                    data["api_key"] = api_key
                    configs_file.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception:
                    continue

        if not found:
            return "not_found"
        return "patched"

    async def run(self, page: Page):
        email = self.account.get("email", "hello@emmarcanjo.com")
        captcha_key = config.captcha.omocaptcha_api_key

        # ── Step 0: Activate CAPTCHA solver extension ──
        if captcha_key:
            self.log("Step 0: Setting OmoCaptcha API key...")
            key_set = False

            # Method 1: Patch configs.json trực tiếp trên disk (không cần mạng)
            try:
                # Lấy profile path từ chrome://version
                version_page = await page.context.new_page()
                try:
                    await version_page.goto("chrome://version", timeout=5000)
                    profile_path = await version_page.evaluate("""() => {
                        const rows = document.querySelectorAll('#inner tr, table tr');
                        for (const row of rows) {
                            const label = row.querySelector('td.label');
                            const value = row.querySelector('td.value, td:nth-child(2)');
                            if (label && value) {
                                const text = label.textContent.trim().toLowerCase();
                                if (text.includes('profile path') || text.includes('đường dẫn cấu hình')) {
                                    return value.textContent.trim();
                                }
                            }
                        }
                        return '';
                    }""")
                    await version_page.close()
                except Exception:
                    profile_path = ""
                    try:
                        await version_page.close()
                    except Exception:
                        pass

                if profile_path:
                    # profile_path = C:\.ADSPOWER_GLOBAL\cache\xxx → root = C:\.ADSPOWER_GLOBAL
                    adspower_root = str(Path(profile_path).parent.parent)
                    self.log(f"   📂 AdsPower root: {adspower_root}")

                    result = self._find_and_patch_omocaptcha_config(adspower_root, captcha_key)
                    if result != "not_found":
                        key_set = True
                        self.log(f"   ✅ OmoCaptcha key {result} (via configs.json)")
                        # Reload extension bằng cách navigate tới extension page
                        try:
                            await page.goto("chrome://extensions", timeout=3000)
                            await self.wait(1, 2)
                        except Exception:
                            pass
                    else:
                        self.log("   ⚠️ configs.json not found in extension dirs")
            except Exception as e:
                self.log(f"   ⚠️ File patch failed: {e.__class__.__name__}: {e}")

            # Method 2: Fallback — navigate to set-key URL
            if not key_set:
                self.log("   ↪ Fallback: trying URL method...")
                set_key_url = f"https://omocaptcha.com/set-key/?api_key={captcha_key}"
                try:
                    await page.goto(
                        set_key_url,
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                    key_set = True
                    self.log("   ✅ OmoCaptcha key set (via URL)")
                except Exception as e:
                    self.log(f"   ⚠️ URL method also failed: {e.__class__.__name__}")
                    self.log("   ↪ Continuing — extension may already be configured")

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
