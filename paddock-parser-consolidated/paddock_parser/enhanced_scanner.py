#!/usr/bin/env python3
"""Paddock Parser Toolkit - Enhanced Scanner & Prefetcher Module (v1.4)
This module is now fully integrated with the "enabled" flag in config.json.
All functions, including the scanner, prefetcher, and connection tester,
will now ignore any data source that is marked as disabled.
"""

import sys
import asyncio
import httpx
import logging
from datetime import date
from pathlib import Path
from typing import Dict, Any, List
import re
import unicodedata

# --- Refactored Imports ---
from .config_manager import config_manager
from .fetching import get_shared_async_client, breadcrumb_get, resilient_get
from . import adapters as Sources


# --- CONFIGURATION HELPERS ---
def build_httpx_client_kwargs() -> Dict[str, Any]:
    """
    Builds kwargs for httpx.AsyncClient with corporate proxy and CA support.
    """
    config = config_manager.get_config()
    http_client = config.get("HTTP_CLIENT", {})
    verify_ssl = http_client.get("VERIFY_SSL", True)
    ca_bundle = http_client.get("CA_BUNDLE")
    proxies = http_client.get("PROXIES")

    verify: Any = ca_bundle if ca_bundle else verify_ssl
    kwargs: Dict[str, Any] = {"verify": verify}
    if proxies:
        kwargs["proxies"] = proxies
    return kwargs


# - Helper Function for Filename Sanitization -
def sanitize_filename(name: str) -> str:
    """Cleans a string to be a valid filename."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s-]", "_", name).strip()
    name = re.sub(r"\s+", "_", name)
    return name


# --- Core Fetching & Parsing Functions ---
async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    """Fetches content from a URL using configured headers."""
    config = config_manager.get_config()
    logging.info(f"Fetching URL: {url}")
    headers = config.get("StealthHeaders", {})  # Using StealthHeaders as per config
    timeout = config.get("HTTP_CLIENT", {}).get("REQUEST_TIMEOUT", 30.0)
    try:
        response = await client.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        logging.info(f"[SUCCESS] Fetched {len(response.text)} chars from {url}")
        return response.text
    except httpx.HTTPStatusError as e:
        logging.error(f"[ERROR] HTTP Error {e.response.status_code} for {url}: {e}")
    except httpx.RequestError as e:
        logging.error(f"[ERROR] Request Error for {url}: {e}")
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error fetching {url}: {e}")
    return ""


# --- Prefetching Logic ---
async def prefetch_source(client: httpx.AsyncClient, site: Dict[str, Any], today_str: str) -> bool:
    """Fetches and saves a single data source to the input directory."""
    config = config_manager.get_config()
    input_dir = Path(config["INPUT_DIR"])
    input_dir.mkdir(exist_ok=True, parents=True)
    url = site["url"].format(date_str_iso=today_str)
    logging.info(f"Prefetching: {site['name']}")
    content = await fetch_url(client, url)
    if content:
        filename = sanitize_filename(site["name"]) + ".html"
        output_path = input_dir / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logging.info(f"[SUCCESS] Saved '{site['name']}' to {output_path}")
            return True
        except Exception as e:
            logging.error(f"[ERROR] Failed to write file for '{site['name']}': {e}")
    return False


async def run_batch_prefetch():
    """Automatically downloads all enabled data sources to the input folder."""
    config = config_manager.get_config()
    logging.info("Starting Automated Pre-Fetch of Enabled Sources...")
    today_str = date.today().strftime("%Y-%m-%d")
    SKIP_LIST = ["(DISABLED)", "IGNORE", "SKIP"]
    adapter_source_ids = [adapter.source_id for adapter in Sources.ADAPTERS]

    async with httpx.AsyncClient(follow_redirects=True, **build_httpx_client_kwargs()) as client:
        prefetch_tasks = []
        for category in config.get("LEGACY_DATA_SOURCES", []):  # Using legacy sources
            logging.info(f"- Processing Category: {category['title']} -")
            sites = [site for site in category.get("sites", []) if site.get("enabled", True)]
            for site in sites:
                site_name = site.get("name", "")
                if any(skip_item in site_name for skip_item in SKIP_LIST):
                    continue
                if any(adapter_id in site_name.lower() for adapter_id in adapter_source_ids):
                    continue
                if site.get("url"):
                    task = asyncio.create_task(prefetch_source(client, site, today_str))
                    prefetch_tasks.append(task)
        results = await asyncio.gather(*prefetch_tasks)
        success_count = sum(1 for r in results if r)
        logging.info(
            f"Automated Pre-Fetch Complete. Success: {success_count}/{len(prefetch_tasks)}"
        )


# --- Connection Testing Logic ---
async def test_scanner_connections():
    """Tests all enabled scanner connections to ensure URLs are reachable."""
    config = config_manager.get_config()
    logging.info("Testing all enabled data source connections...")
    today_str = date.today().strftime("%Y-%m-%d")
    headers = config.get("StealthHeaders", {})
    async with httpx.AsyncClient(headers=headers, **build_httpx_client_kwargs()) as client:
        for category in config.get("LEGACY_DATA_SOURCES", []):
            logging.info(f"- Testing Category: {category['title']} -")
            sites = [site for site in category.get("sites", []) if site.get("enabled", True)]
            for site in sites:
                if site.get("url"):
                    url = site["url"].format(date_str_iso=today_str)
                    try:
                        async with client.stream(
                            "GET", url, timeout=15.0, follow_redirects=True
                        ) as response:
                            status_code = response.status_code
                        if 200 <= status_code < 400:
                            logging.info(f"[SUCCESS] ({status_code}) - {site['name']}")
                        else:
                            logging.warning(f"[WARNING] ({status_code}) - {site['name']} at {url}")
                    except httpx.RequestError as e:
                        logging.error(
                            f"[ERROR] FAILED - {site['name']} at {url} ({type(e).__name__})"
                        )


# --- New scanner/discovery functions ---
API_URL_RE = re.compile(r'https?://[^"\']*(?:api|json|live|odds)[^"\']*', re.I)


async def fetch_with_favicon(base_url: str, target_url: str):
    config = config_manager.get_config()
    features = config.get("ScraperFeatures", {})
    if not features.get("enable_favicon_prefetch"):
        return await resilient_get(target_url)
    client = get_shared_async_client()
    await asyncio.gather(
        client.get(f"{base_url.rstrip('/')}/favicon.ico"), resilient_get(target_url)
    )


async def discover_rss(base_url: str) -> List[str]:
    config = config_manager.get_config()
    features = config.get("ScraperFeatures", {})
    if not features.get("enable_rss_discovery"):
        return []
    client = get_shared_async_client()
    found = []
    for suf in ("rss", "feed", "xml"):
        try:
            r = await client.get(f"{base_url.rstrip('/')}/{suf}", timeout=8.0)
            if r.status_code == 200 and (
                "xml" in r.headers.get("content-type", "").lower() or "<rss" in r.text[:256].lower()
            ):
                found.append(str(r.url))
        except Exception:
            pass
    return found


async def scan_js_for_endpoints(html: str, base_url: str) -> List[str]:
    config = config_manager.get_config()
    features = config.get("ScraperFeatures", {})
    if not features.get("enable_js_endpoint_scan"):
        return []
    urls = list(set(API_URL_RE.findall(html)))
    return urls


async def fetch_breadcrumb_page(base_url: str, *path_parts: str) -> str:
    urls = [base_url.rstrip("/")]
    for part in path_parts:
        urls.append(f"{urls[-1]}/{part}")
    resp = await breadcrumb_get(urls)
    return resp.text


# --- Main Execution Guard ---
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stdout
    )
    asyncio.run(run_batch_prefetch())
