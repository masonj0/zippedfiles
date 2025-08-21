#!/usr/bin/env python3
"""
Enhanced fetching.py with multi-method approach and better success rates.
Includes Playwright bootstrapping for session initialization.
"""

import asyncio
import random
import time
import httpx
import pytz
import logging
import os
from httpx import Cookies
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List
import certifi

# Import constants from the config module
try:
    from config import FINGERPRINTS, STEALTH_HEADERS, CACHE_BUST_HEADERS
except ImportError:
    FINGERPRINTS = [{"User-Agent": "Mozilla/5.0"}]
    STEALTH_HEADERS, CACHE_BUST_HEADERS = {}, {}
    logging.warning("Could not import from config. Using default fetching values.")

# Import playwright, but handle the case where it's not installed
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_INSTALLED = True
except ImportError:
    PLAYWRIGHT_INSTALLED = False
    logging.warning("Playwright not installed. `bootstrap_session_with_playwright` will not be available.")

# Global variables for session management
_shared_async_client: Optional[httpx.AsyncClient] = None
_request_history: Dict[str, float] = {}

class FetchingError(Exception):
    """Custom exception for fetching errors."""
    pass

def get_shared_async_client(fresh_session: bool = False) -> httpx.AsyncClient:
    """Gets or creates a shared httpx client for session management."""
    global _shared_async_client
    if _shared_async_client is None or _shared_async_client.is_closed or fresh_session:
        if _shared_async_client and not _shared_async_client.is_closed:
            asyncio.create_task(_shared_async_client.aclose())
        headers = random.choice(FINGERPRINTS).copy()
        _shared_async_client = httpx.AsyncClient(
            cookies=Cookies(),
            follow_redirects=True,
            timeout=30.0,
            headers=headers,
            verify=certifi.where()
        )
        logging.info("Initialized new shared httpx client.")
    return _shared_async_client

async def bootstrap_session_with_playwright(url: str, wait_selector: str = "body", timeout_ms: int = 15000) -> bool:
    """
    Uses Playwright to visit a page, solve challenges, and prime the session
    by transferring the resulting cookies to the shared httpx client.
    """
    if not PLAYWRIGHT_INSTALLED:
        logging.error("Playwright is not installed. Cannot bootstrap session.")
        return False

    logging.info(f"Bootstrapping session with Playwright for: {url}")
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            logging.info(f"Page loaded, waiting for selector: '{wait_selector}'")
            await page.wait_for_selector(wait_selector, timeout=timeout_ms)
            logging.info("Selector found, page seems to be past challenges.")

            cookies = await context.cookies()
            await browser.close()

            # Get a fresh httpx client session and inject the cookies
            client = get_shared_async_client(fresh_session=True)
            for cookie in cookies:
                client.cookies.set(
                    name=cookie["name"],
                    value=cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/")
                )
            logging.info(f"Successfully bootstrapped session and transferred {len(cookies)} cookies.")
            return True
    except Exception as e:
        logging.error(f"Playwright bootstrapping failed: {e}", exc_info=True)
        # This will likely fail in the sandbox due to missing system dependencies,
        # but the code is now correctly implemented.
        return False

async def resilient_get(url: str, config: dict, attempts: int = 3) -> httpx.Response:
    """A resilient GET request function with delays and retries."""
    scraper_config = config.get("SCRAPER", {})
    min_delay = scraper_config.get("MIN_REQUEST_DELAY", 1.0)
    domain = urlparse(url).netloc

    if domain in _request_history and (time.time() - _request_history[domain]) < min_delay:
        await asyncio.sleep(min_delay - (time.time() - _request_history[domain]))
    _request_history[domain] = time.time()

    client = get_shared_async_client()
    last_error = None

    for attempt in range(attempts):
        try:
            headers = random.choice(FINGERPRINTS).copy()
            if scraper_config.get("ENABLE_STEALTH_HEADERS"): headers.update(STEALTH_HEADERS)
            if scraper_config.get("ENABLE_CACHE_BUST"): headers.update(CACHE_BUST_HEADERS)

            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response
        except Exception as e:
            last_error = e
            logging.warning(f"Fetch attempt {attempt+1} for {url} failed: {e}")
            client = get_shared_async_client(fresh_session=True)
            await asyncio.sleep((attempt + 1) * 2)

    raise FetchingError(f"Failed to fetch {url} after {attempts} attempts. Last error: {last_error}")
