"""
AdsPower Local API Client.
Docs: https://localapi-doc-en.adspower.com/
"""

import asyncio
import logging
from typing import Optional

import httpx

from config import AdsPowerConfig

logger = logging.getLogger(__name__)


class AdsPowerError(Exception):
    """AdsPower API error."""
    pass


class AdsPowerClient:
    """Client for AdsPower Local API."""

    def __init__(self, config: AdsPowerConfig):
        self.base_url = config.base_url
        self.api_key = getattr(config, "api_key", "")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make a request to AdsPower API and return the parsed response."""
        url = f"{self.base_url}{path}"

        # Inject API key into query params
        if self.api_key:
            params = kwargs.get("params", {}) or {}
            params["api_key"] = self.api_key
            kwargs["params"] = params

        try:
            resp = await self._client.request(method, url, **kwargs)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise AdsPowerError(
                    f"API error [{data.get('code')}]: {data.get('msg', 'Unknown error')}"
                )
            return data.get("data", {})

        except httpx.HTTPError as e:
            raise AdsPowerError(f"HTTP error: {e}") from e

    # ──────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────

    async def check_status(self) -> bool:
        """Kiểm tra AdsPower có đang chạy không."""
        try:
            # Note: /status is at root, not under /api/v1/
            url = f"{self.base_url}/status"
            resp = await self._client.get(url, timeout=5)
            data = resp.json()
            if data.get("code") == 0:
                logger.info("AdsPower status: OK")
                return True
            return False
        except Exception as e:
            logger.error(f"AdsPower not reachable: {e}")
            return False

    # ──────────────────────────────────────────────
    # Profile Management
    # ──────────────────────────────────────────────

    async def create_profile(
        self,
        name: str = "",
        group_id: str = "0",
        proxy_config: Optional[dict] = None,
        fingerprint_config: Optional[dict] = None,
    ) -> dict:
        """
        Tạo profile mới.

        Args:
            name: Tên profile (nếu trống sẽ auto-generate)
            group_id: ID nhóm profile
            proxy_config: Cấu hình proxy, ví dụ:
                {
                    "proxy_type": "http",       # http | socks5 | https
                    "proxy_host": "1.2.3.4",
                    "proxy_port": "8080",
                    "proxy_user": "user",
                    "proxy_password": "pass"
                }
            fingerprint_config: Cấu hình fingerprint tùy chỉnh

        Returns:
            dict chứa profile info (bao gồm "id")
        """
        payload = {
            "group_id": group_id,
            "remark": name,
        }

        if proxy_config:
            payload["user_proxy_config"] = proxy_config

        if fingerprint_config:
            payload["fingerprint_config"] = fingerprint_config

        data = await self._request("POST", "/api/v1/user/create", json=payload)
        profile_id = data.get("id", "")
        logger.info(f"Created profile: {profile_id} (name={name})")
        return data

    async def delete_profile(self, profile_ids: list[str]) -> bool:
        """Xóa profiles theo danh sách IDs."""
        data = await self._request(
            "POST",
            "/api/v1/user/delete",
            json={"user_ids": profile_ids},
        )
        logger.info(f"Deleted profiles: {profile_ids}")
        return True

    async def list_profiles(
        self,
        page: int = 1,
        page_size: int = 100,
        group_id: str = "",
    ) -> list[dict]:
        """Liệt kê các profiles."""
        params = {"page": page, "page_size": page_size}
        if group_id:
            params["group_id"] = group_id

        data = await self._request("GET", "/api/v1/user/list", params=params)
        profiles = data.get("list", [])
        logger.info(f"Listed {len(profiles)} profiles (page={page})")
        return profiles

    async def update_profile(self, profile_id: str, **kwargs) -> dict:
        """Cập nhật thông tin profile."""
        payload = {"user_id": profile_id, **kwargs}
        data = await self._request("POST", "/api/v1/user/update", json=payload)
        logger.info(f"Updated profile: {profile_id}")
        return data

    # ──────────────────────────────────────────────
    # Browser Control
    # ──────────────────────────────────────────────

    async def start_profile(
        self,
        profile_id: str,
        headless: bool = False,
        open_tabs: int = 0,
    ) -> dict:
        """
        Mở browser cho profile.

        Args:
            profile_id: ID profile cần mở
            headless: Chạy headless mode
            open_tabs: Số tab cần mở (0 = mặc định)

        Returns:
            dict chứa WebSocket endpoints:
                {
                    "ws": {
                        "puppeteer": "ws://...",
                        "selenium": "..."
                    },
                    "debug_port": "...",
                    "webdriver": "..."
                }
        """
        params = {
            "user_id": profile_id,
            "open_tabs": open_tabs,
        }
        if headless:
            params["headless"] = 1

        data = await self._request("GET", "/api/v1/browser/start", params=params)
        logger.info(
            f"Started profile: {profile_id} | "
            f"debug_port={data.get('debug_port', 'N/A')}"
        )
        return data

    async def stop_profile(self, profile_id: str) -> bool:
        """Đóng browser của profile."""
        try:
            await self._request(
                "GET",
                "/api/v1/browser/stop",
                params={"user_id": profile_id},
            )
            logger.info(f"Stopped profile: {profile_id}")
            return True
        except AdsPowerError as e:
            logger.warning(f"Error stopping profile {profile_id}: {e}")
            return False

    async def check_profile_active(self, profile_id: str) -> bool:
        """Kiểm tra profile có đang chạy không."""
        try:
            data = await self._request(
                "GET",
                "/api/v1/browser/active",
                params={"user_id": profile_id},
            )
            status = data.get("status", "Inactive")
            return status == "Active"
        except AdsPowerError:
            return False

    # ──────────────────────────────────────────────
    # Convenience Methods
    # ──────────────────────────────────────────────

    async def create_and_start(
        self,
        name: str = "",
        proxy_config: Optional[dict] = None,
        headless: bool = False,
    ) -> tuple[str, dict]:
        """
        Tạo profile mới và mở browser, trả về (profile_id, browser_data).
        Tiện dùng cho quick automation.
        """
        profile = await self.create_profile(name=name, proxy_config=proxy_config)
        profile_id = profile["id"]
        browser_data = await self.start_profile(profile_id, headless=headless)
        return profile_id, browser_data

    async def stop_and_delete(self, profile_id: str) -> bool:
        """Đóng browser và xóa profile. Dùng để cleanup."""
        await self.stop_profile(profile_id)
        await asyncio.sleep(1)  # Chờ browser đóng hoàn toàn
        return await self.delete_profile([profile_id])

    @staticmethod
    def build_proxy_config(
        proxy_str: str,
        proxy_type: str = "http",
    ) -> dict:
        """
        Parse proxy string thành proxy config cho AdsPower.

        Supports formats:
            - host:port:user:pass
            - host:port
            - http://user:pass@host:port
            - socks5://user:pass@host:port
        """
        proxy_str = proxy_str.strip()

        # Format: protocol://user:pass@host:port
        if "://" in proxy_str:
            from urllib.parse import urlparse
            parsed = urlparse(proxy_str)
            return {
                "proxy_type": parsed.scheme or proxy_type,
                "proxy_host": parsed.hostname or "",
                "proxy_port": str(parsed.port or ""),
                "proxy_user": parsed.username or "",
                "proxy_password": parsed.password or "",
            }

        parts = proxy_str.split(":")

        # Format: host:port
        if len(parts) == 2:
            return {
                "proxy_type": proxy_type,
                "proxy_host": parts[0],
                "proxy_port": parts[1],
                "proxy_user": "",
                "proxy_password": "",
            }

        # Format: host:port:user:pass
        if len(parts) == 4:
            return {
                "proxy_type": proxy_type,
                "proxy_host": parts[0],
                "proxy_port": parts[1],
                "proxy_user": parts[2],
                "proxy_password": parts[3],
            }

        raise ValueError(f"Invalid proxy format: {proxy_str}")
