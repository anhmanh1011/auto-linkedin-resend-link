"""
KiotProxy client — tích hợp API Kiot Proxy.

API Docs: https://api.kiotproxy.com/swagger-ui/index.html

Mỗi proxy key = 1 worker. Key tự xoay IP mỗi phút.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger("kiotproxy")

KIOT_API_BASE = "https://api.kiotproxy.com"


class KiotProxyClient:
    """Client gọi API Kiot Proxy để lấy proxy info."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=KIOT_API_BASE,
            timeout=15.0,
        )

    async def close(self):
        await self._client.aclose()

    async def get_new_proxy(self, key: str) -> Optional[dict]:
        """
        Gọi API lấy proxy MỚI (xoay IP).

        Returns dict: {host, port, user, pass} hoặc None nếu lỗi.
        """
        try:
            resp = await self._client.get(
                "/api/v1/proxies/new",
                params={"key": key},
            )
            data = resp.json()

            if data.get("success") and data.get("data"):
                proxy_data = data["data"]
                result = {
                    "host": proxy_data.get("host", ""),
                    "port": str(proxy_data.get("httpPort", "")),
                    "user": proxy_data.get("proxyUser", ""),
                    "pass": proxy_data.get("proxyPass", ""),
                }
                logger.info(
                    f"  Proxy: {result['host']}:{result['port']} "
                    f"(IP: {proxy_data.get('realIpAddress', 'N/A')})"
                )
                return result
            else:
                msg = data.get("message", "Unknown error")
                logger.warning(f"  KiotProxy error: {msg}")
                return None

        except Exception as e:
            logger.error(f"  KiotProxy API failed: {e}")
            return None

    async def get_current_proxy(self, key: str) -> Optional[dict]:
        """Lấy proxy hiện tại (không xoay IP)."""
        try:
            resp = await self._client.get(
                "/api/v1/proxies/current",
                params={"key": key},
            )
            data = resp.json()

            if data.get("success") and data.get("data"):
                proxy_data = data["data"]
                return {
                    "host": proxy_data.get("host", ""),
                    "port": str(proxy_data.get("httpPort", "")),
                    "user": proxy_data.get("proxyUser", ""),
                    "pass": proxy_data.get("proxyPass", ""),
                }
            return None

        except Exception as e:
            logger.error(f"  KiotProxy API failed: {e}")
            return None

    async def release_proxy(self, key: str) -> bool:
        """Trả proxy key (out key)."""
        try:
            resp = await self._client.get(
                "/api/v1/proxies/out",
                params={"key": key},
            )
            data = resp.json()
            return data.get("success", False)
        except Exception:
            return False
