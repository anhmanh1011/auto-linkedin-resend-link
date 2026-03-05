"""
Test script — build & run thử automation-base.
Chạy: python3 test_run.py
"""

import asyncio
import logging
import sys

# ── Setup logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_run")


def test_config():
    """Test 1: Load config từ environment."""
    logger.info("=" * 50)
    logger.info("TEST 1: Config Loading")
    logger.info("=" * 50)

    from config import Config, config

    logger.info(f"  AdsPower URL : {config.adspower.base_url}")
    logger.info(f"  Captcha      : provider={config.captcha.provider}, timeout={config.captcha.timeout}s")
    logger.info(f"  Proxy        : file={config.proxy.proxy_file}, strategy={config.proxy.rotation_strategy}")
    logger.info(f"  Engine       : workers={config.engine.max_workers}, retries={config.engine.max_retries}")
    logger.info(f"  Screenshot   : {config.engine.screenshot_dir}")

    # Test from_env
    c2 = Config.from_env()
    assert c2.adspower.host == "local.adspower.net"
    assert c2.adspower.port == 50325
    assert c2.adspower.api_key == "eb9637d4bb4c9b674ff5f68232724a5d"
    logger.info("  ✅ Config loaded OK")


def test_proxy_parser():
    """Test 2: Parse các định dạng proxy."""
    logger.info("")
    logger.info("=" * 50)
    logger.info("TEST 2: Proxy Parser")
    logger.info("=" * 50)

    from adspower_client import AdsPowerClient

    # Format: host:port
    p1 = AdsPowerClient.build_proxy_config("1.2.3.4:8080")
    assert p1["proxy_host"] == "1.2.3.4"
    assert p1["proxy_port"] == "8080"
    assert p1["proxy_type"] == "http"
    logger.info(f"  host:port         → {p1}")

    # Format: host:port:user:pass
    p2 = AdsPowerClient.build_proxy_config("1.2.3.4:8080:admin:secret")
    assert p2["proxy_user"] == "admin"
    assert p2["proxy_password"] == "secret"
    logger.info(f"  host:port:u:p     → {p2}")

    # Format: http://user:pass@host:port
    p3 = AdsPowerClient.build_proxy_config("http://user:pass@10.0.0.1:3128")
    assert p3["proxy_host"] == "10.0.0.1"
    assert p3["proxy_port"] == "3128"
    assert p3["proxy_user"] == "user"
    logger.info(f"  http://u:p@h:port → {p3}")

    # Format: socks5://
    p4 = AdsPowerClient.build_proxy_config("socks5://abc:xyz@192.168.1.1:1080")
    assert p4["proxy_type"] == "socks5"
    logger.info(f"  socks5://...      → {p4}")

    # Invalid format
    try:
        AdsPowerClient.build_proxy_config("invalid")
        assert False, "Should raise ValueError"
    except ValueError as e:
        logger.info(f"  invalid format    → Caught: {e}")

    logger.info("  ✅ Proxy parser OK")


async def test_client_creation():
    """Test 3: Khởi tạo client và thử connect."""
    logger.info("")
    logger.info("=" * 50)
    logger.info("TEST 3: Client Creation & Connection")
    logger.info("=" * 50)

    from config import AdsPowerConfig
    from adspower_client import AdsPowerClient

    cfg = AdsPowerConfig()
    logger.info(f"  Target: {cfg.base_url}")

    async with AdsPowerClient(cfg) as client:
        logger.info("  ✅ Client created OK")

        # Thử connect đến AdsPower (có thể fail nếu AdsPower chưa chạy)
        logger.info("  Checking AdsPower connection...")
        is_running = await client.check_status()

        if is_running:
            logger.info("  ✅ AdsPower is running!")

            # Thử list profiles
            profiles = await client.list_profiles(page_size=5)
            logger.info(f"  Found {len(profiles)} profiles")
            for p in profiles[:3]:
                logger.info(f"    - {p.get('name', 'N/A')} (id={p.get('user_id', 'N/A')})")
        else:
            logger.warning("  ⚠️  AdsPower is NOT running on localhost:50325")
            logger.info("  (This is expected if AdsPower app is not open)")

    logger.info("  ✅ Client cleanup OK")


def main():
    logger.info("🚀 automation-base — Build & Run Test")
    logger.info(f"   Python {sys.version}")
    logger.info("")

    # Test 1: Config
    test_config()

    # Test 2: Proxy parser
    test_proxy_parser()

    # Test 3: Client (async)
    asyncio.run(test_client_creation())

    logger.info("")
    logger.info("=" * 50)
    logger.info("🎉 All tests passed!")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
