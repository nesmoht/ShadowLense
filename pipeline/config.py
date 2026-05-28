"""Configuration — reads environment variables and exposes typed settings."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # Anthropic
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ["ANTHROPIC_API_KEY"]
    )
    # model: str = "claude-opus-4-7"  # ~$3-8/run
    model: str = "claude-sonnet-4-6"  # ~$0.50-1.50/run

    # SendGrid
    sendgrid_api_key: str = field(
        default_factory=lambda: os.getenv("SENDGRID_API_KEY", "")
    )
    alert_from_email: str = field(
        default_factory=lambda: os.getenv("ALERT_FROM_EMAIL", "alerts@example.com")
    )

    # Tor proxy
    tor_proxy_host: str = field(
        default_factory=lambda: os.getenv("TOR_PROXY_HOST", "127.0.0.1")
    )
    tor_proxy_port: int = field(
        default_factory=lambda: int(os.getenv("TOR_PROXY_PORT", "9050"))
    )

    # Storage
    data_dir: str = field(
        default_factory=lambda: os.getenv("DATA_DIR", "./data")
    )

    # Alert domains to watch (comma-separated env var or extend here)
    alert_domains: List[str] = field(
        default_factory=lambda: [
            d.strip()
            for d in os.getenv("ALERT_DOMAINS", "").split(",")
            if d.strip()
        ]
    )

    # Alert recipient
    alert_to_email: str = field(
        default_factory=lambda: os.getenv("ALERT_TO_EMAIL", "security@example.com")
    )

    # Clearnet / onion sources to crawl
    sources: List[dict] = field(default_factory=lambda: [
        {
            "url": "https://ahmia.fi/search/?q=malware+for+sale",
            "source_type": "ahmia_search",
            "use_tor": False,
        },
        {
            "url": "https://urlhaus-api.abuse.ch/v1/urls/recent/",
            "source_type": "urlhaus_api",
            "use_tor": False,
        },
        {
            "url": "https://bazaar.abuse.ch/api/",
            "source_type": "malware_bazaar",
            "use_tor": False,
        },
    ])

    @property
    def bronze_dir(self) -> str:
        return os.path.join(self.data_dir, "bronze")

    @property
    def silver_dir(self) -> str:
        return os.path.join(self.data_dir, "silver")

    @property
    def gold_dir(self) -> str:
        return os.path.join(self.data_dir, "gold")
