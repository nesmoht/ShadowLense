"""Tor-aware HTTP client for fetching pages via SOCKS5 proxy."""

from datetime import datetime, timezone
from typing import Any

import requests


def fetch(
    url: str,
    use_tor: bool = False,
    proxy_host: str = "127.0.0.1",
    proxy_port: int = 9050,
) -> dict[str, Any]:
    """Fetch a URL, optionally routing through a Tor SOCKS5 proxy.

    Returns a dict with keys: url, status_code, content, fetched_at.
    On any exception, status_code is 0 and content contains the error message.
    """
    proxies = None
    if use_tor:
        proxy_url = f"socks5h://{proxy_host}:{proxy_port}"
        proxies = {"http": proxy_url, "https": proxy_url}

    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        response = requests.get(url, proxies=proxies, timeout=30)
        return {
            "url": url,
            "status_code": response.status_code,
            "content": response.text,
            "fetched_at": fetched_at,
        }
    except Exception as exc:
        return {
            "url": url,
            "status_code": 0,
            "content": f"ERROR: {exc}",
            "fetched_at": fetched_at,
        }
