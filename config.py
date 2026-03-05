"""
Configuration module for the automation base project.
Loads settings from environment variables or .env file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class AdsPowerConfig:
    """AdsPower Local API configuration."""
    host: str = "local.adspower.net"
    port: int = 50325
    api_key: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class CaptchaConfig:
    """CAPTCHA solver configuration."""
    # Chọn solver: "2captcha" hoặc "capsolver"
    provider: str = "2captcha"
    api_key: str = ""
    # Timeout chờ giải captcha (giây)
    timeout: int = 120
    # Polling interval (giây)
    poll_interval: int = 5


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    # Đường dẫn file chứa danh sách proxy (mỗi dòng 1 proxy)
    proxy_file: str = "proxies.txt"
    # Chiến lược rotation: "round_robin" hoặc "random"
    rotation_strategy: str = "round_robin"
    # Loại proxy mặc định: "http", "socks5"
    default_type: str = "http"


@dataclass
class EngineConfig:
    """Automation engine configuration."""
    # Số worker chạy đồng thời
    max_workers: int = 5
    # Delay giữa các task (giây) — random trong khoảng [min, max]
    task_delay_min: float = 3.0
    task_delay_max: float = 8.0
    # Delay giữa các action trong browser (giây)
    action_delay_min: float = 1.0
    action_delay_max: float = 3.0
    # Số lần retry khi gặp lỗi
    max_retries: int = 3
    # Thư mục lưu screenshots
    screenshot_dir: str = "screenshots"


@dataclass
class Config:
    """Main configuration — tổng hợp tất cả settings."""
    adspower: AdsPowerConfig = field(default_factory=AdsPowerConfig)
    captcha: CaptchaConfig = field(default_factory=CaptchaConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """Load config từ environment variables."""
        return cls(
            adspower=AdsPowerConfig(
                host=os.getenv("ADSPOWER_HOST", "local.adspower.net"),
                port=int(os.getenv("ADSPOWER_PORT", "50325")),
                api_key=os.getenv("ADSPOWER_API_KEY", ""),
            ),
            captcha=CaptchaConfig(
                provider=os.getenv("CAPTCHA_PROVIDER", "2captcha"),
                api_key=os.getenv("CAPTCHA_API_KEY", ""),
                timeout=int(os.getenv("CAPTCHA_TIMEOUT", "120")),
                poll_interval=int(os.getenv("CAPTCHA_POLL_INTERVAL", "5")),
            ),
            proxy=ProxyConfig(
                proxy_file=os.getenv("PROXY_FILE", "proxies.txt"),
                rotation_strategy=os.getenv("PROXY_ROTATION", "round_robin"),
                default_type=os.getenv("PROXY_TYPE", "http"),
            ),
            engine=EngineConfig(
                max_workers=int(os.getenv("MAX_WORKERS", "5")),
                task_delay_min=float(os.getenv("TASK_DELAY_MIN", "3.0")),
                task_delay_max=float(os.getenv("TASK_DELAY_MAX", "8.0")),
                action_delay_min=float(os.getenv("ACTION_DELAY_MIN", "1.0")),
                action_delay_max=float(os.getenv("ACTION_DELAY_MAX", "3.0")),
                max_retries=int(os.getenv("MAX_RETRIES", "3")),
                screenshot_dir=os.getenv("SCREENSHOT_DIR", "screenshots"),
            ),
        )

    def ensure_dirs(self):
        """Tạo các thư mục cần thiết."""
        Path(self.engine.screenshot_dir).mkdir(parents=True, exist_ok=True)


# Global config instance
config = Config.from_env()
