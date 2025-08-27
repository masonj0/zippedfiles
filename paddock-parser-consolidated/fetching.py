# fetching.py (refactored with GPT5 plan)
from __future__ import annotations
import asyncio
import random
import time
import httpx
from httpx import Cookies
from typing import Optional, List, Dict
import hashlib

try:
    from zoneinfo import ZoneInfo
except ImportError:
    pass  # fallback if running on <3.9

# Import from the new config structure
from config import (
    HTTP as HTTP_CFG,
    ScraperFeatures as FEATURES,
    Proxies as PROXY_CFG,
    Fingerprints as FP_LIST,
    StealthHeaders as STEALTH,
    CacheBustHeaders as NOCACHE,
    DNSResolvers as DNS_RESOLVERS,
)


# Custom Exceptions
class FetchingError(Exception):
    """Custom exception for fetching errors."""

    pass


class BlockingDetectedError(FetchingError):
    """Raised when blocking or anti-bot measures are detected."""

    pass


# --- New implementation from GPT5 plan ---

_shared_async_client: Optional[httpx.AsyncClient] = None


def _pick_proxy() -> Optional[str]:
    if PROXY_CFG.get("enabled") and PROXY_CFG.get("pool"):
        return random.choice(PROXY_CFG["pool"])
    return None


def _pick_fingerprint() -> Dict[str, str]:
    if FEATURES.get("enable_fingerprint_rotation") and FP_LIST:
        return random.choice(FP_LIST)
    return {}


def _base_headers(extra: Dict[str, str] | None = None) -> Dict[str, str]:
    h = {}
    if FEATURES.get("enable_stealth_headers"):
        h.update(STEALTH)
    h.update(_pick_fingerprint())
    if FEATURES.get("enable_cache_bust"):
        h.update(NOCACHE)
    if extra:
        h.update(extra)
    return h


def get_shared_async_client(extra_headers: Dict[str, str] | None = None) -> httpx.AsyncClient:
    global _shared_async_client
    if _shared_async_client is None or _shared_async_client.is_closed:
        _shared_async_client = httpx.AsyncClient(
            cookies=Cookies(),
            follow_redirects=bool(HTTP_CFG.get("follow_redirects", True)),
            http2=bool(HTTP_CFG.get("http2", True)),
            timeout=httpx.Timeout(15.0, connect=10.0),
            proxies=_pick_proxy(),
            headers=_base_headers(extra_headers),
        )
    return _shared_async_client


async def close_shared_async_client():
    global _shared_async_client
    if _shared_async_client is not None:
        await _shared_async_client.aclose()
        _shared_async_client = None


async def human_pause():
    await asyncio.sleep(
        random.uniform(HTTP_CFG.get("min_delay_sec", 0.5), HTTP_CFG.get("max_delay_sec", 2.0))
    )


async def breadcrumb_get(
    urls: List[str], extra_headers: Dict[str, str] | None = None
) -> httpx.Response:
    client = get_shared_async_client()
    last = None
    for i, u in enumerate(urls):
        headers = _base_headers(extra_headers)
        if i > 0:
            headers["Referer"] = urls[i - 1]
        await human_pause()
        last = await client.get(u, headers=headers)
        if FEATURES.get("enable_timing_content_fingerprints"):
            _monitor_response(u, last)
        if last.status_code >= 400:
            last.raise_for_status()
    return last


async def resilient_get(
    url: str, extra_headers: Dict[str, str] | None = None, attempts: int = 4
) -> httpx.Response:
    client = get_shared_async_client()
    delay = 1.0
    last_error = None
    for i in range(attempts):
        await human_pause()
        headers = _base_headers(extra_headers)
        try:
            r = await client.get(url, headers=headers)
            if FEATURES.get("enable_timing_content_fingerprints"):
                _monitor_response(url, r)
            if r.status_code == 200:
                return r

            r.raise_for_status()

        except httpx.HTTPStatusError as e:
            last_error = e
            if FEATURES.get("enable_error_code_psychology"):
                if e.response.status_code == 403:
                    await asyncio.sleep(67 + random.uniform(0, 6))
                elif e.response.status_code == 429:
                    await asyncio.sleep(delay + random.uniform(0, 30))
                    delay *= 2
                else:
                    await asyncio.sleep(1.0 + i)
            else:
                await asyncio.sleep(1.0 + i)
        except Exception as e:
            last_error = e
            await asyncio.sleep(1.0 + i)

    raise FetchingError(
        f"Failed to fetch {url} after {attempts} attempts. Last error: {last_error}"
    )


# Simple timing/content fingerprint monitor
_content_index: Dict[str, Dict[str, float | str]] = {}


def _monitor_response(url: str, resp: httpx.Response):
    try:
        fp = hashlib.md5(resp.text.encode("utf-8")).hexdigest()[:8]
    except Exception:
        fp = "NA"
    now = time.time()
    prev = _content_index.get(url)
    _content_index[url] = {"fp": fp, "ts": now, "status": str(resp.status_code)}
    # Optionally: log suspiciously fast responses or long-term unchanged content.


# DNS multi-resolver check (safe, read-only)
async def resolve_multi(hostname: str) -> Dict[str, List[str]]:
    try:
        import dns.resolver
    except ImportError:
        return {}
    results: Dict[str, List[str]] = {}
    for server in DNS_RESOLVERS:
        try:
            r = dns.resolver.Resolver(configure=False)
            r.nameservers = [server]
            answers = r.resolve(hostname, "A", lifetime=3.0)
            results[server] = [a.to_text() for a in answers]
        except Exception:
            results[server] = []
    return results
