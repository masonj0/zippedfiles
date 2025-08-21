#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Advanced Fetching Module (V2)

This module provides a resilient, configurable, and high-fidelity fetching
client for all adapters. It uses advanced techniques like browser fingerprint
rotation and robust retry logic to maximize data collection success.
"""

import asyncio
import logging
import random
from typing import Dict, Any, Optional

import httpx
from httpx_socks import AsyncProxyTransport
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config_manager import config_manager

# --- Browser Fingerprint Management ---

def get_fingerprint() -> Dict[str, str]:
    """
    Selects a random browser fingerprint from the config to use for requests.
    """
    config = config_manager.get_config()
    fingerprints = config.get("FINGERPRINTS")
    if not fingerprints:
        logging.warning("No FINGERPRINTS found in config, using a single default fingerprint.")
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
        }
    return random.choice(fingerprints)

# --- HTTP Client Factory ---

def get_http_client(**kwargs) -> httpx.AsyncClient:
    """
    Constructs an `httpx.AsyncClient` with settings from the configuration.
    """
    client_config = config_manager.get_config().get("HTTP_CLIENT", {})

    proxy_url = client_config.get("PROXY")

    transport = None
    if proxy_url:
        try:
            if proxy_url.startswith("socks"):
                transport = AsyncProxyTransport.from_url(proxy_url)
                logging.info(f"Using SOCKS5 proxy transport: {proxy_url.split('@')[1] if '@' in proxy_url else proxy_url}")
            else:
                kwargs['proxies'] = proxy_url
                logging.info(f"Using HTTP/S proxy: {proxy_url}")
        except Exception as e:
            logging.error(f"Failed to configure proxy transport for '{proxy_url}': {e}", exc_info=True)
            transport = None
            if 'proxies' in kwargs:
                del kwargs['proxies']

    final_kwargs = {
        "timeout": client_config.get("REQUEST_TIMEOUT", 20),
        "verify": client_config.get("VERIFY_SSL", True),
        "follow_redirects": True,
        "transport": transport,
        **kwargs,
    }

    return httpx.AsyncClient(**final_kwargs)

# --- Resilient Fetcher ---

class ResilientFetcher:
    """
    A wrapper around the HTTP client that provides automated retries.
    """
    def __init__(self, **client_kwargs):
        self.client_kwargs = client_kwargs
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = get_http_client(**self.client_kwargs)
        return self._client

    @retry(
        stop=stop_after_attempt(config_manager.get_config().get("SCRAPER", {}).get("MAX_RETRIES", 3)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=lambda retry_state: logging.warning(
            f"Retrying request for '{retry_state.args[1]}' "
            f"(attempt {retry_state.attempt_number}): {retry_state.outcome.exception()}"
        ),
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Performs a GET request with retries on failure.
        """
        client = await self._get_client()

        request_headers = {**get_fingerprint(), **kwargs.pop("headers", {})}

        logging.info(f"Fetching URL: {url} with User-Agent: {request_headers.get('User-Agent')}")

        response = await client.get(url, headers=request_headers, **kwargs)
        response.raise_for_status()

        return response

    async def close(self):
        """Closes the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
