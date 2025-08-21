#!/usr/bin/env python3
"""Paddock Parser Toolkit - Enhanced Scanner & Prefetcher Module (v1.4)
This module is now fully integrated with the "enabled" flag in config.json.
All functions, including the scanner, prefetcher, and connection tester,
will now ignore any data source that is marked as disabled.

Future Exploration Ideas:
- When making HTTP requests, consider setting the 'Referer' header to a common
  source like 'https://www.google.com/' or the base URL of the target site
  itself, as many APIs check this.
- For sites that are difficult to scrape, inspect the Network tab in browser
  developer tools for hidden API calls, as we discovered with Sporting Life
  and UKRacingForm.
"""
import sys
import asyncio
import httpx
import logging
from datetime import date
from pathlib import Path
from typing import Dict, Any
import re
import unicodedata

# Import the configuration loader
try:
    from .config import load_config
except ImportError:
    print("FATAL: Could not import config.py. Ensure it's in the same directory.", file=sys.stderr)
    sys.exit(1)

# Shared Intelligence: Ensure all normalization is consistent
# Note: Imports from normalizer were removed as they were unused in this module.

# --- CONFIGURATION HELPERS ---
def build_httpx_client_kwargs(config: Dict) -> Dict[str, Any]:
    """
    Builds kwargs for httpx.AsyncClient with corporate proxy and CA support.
    - HTTP_CLIENT.VERIFY_SSL: bool (default True)
    - HTTP_CLIENT.CA_BUNDLE: path to corporate root CA (optional)
    - HTTP_CLIENT.PROXIES: dict or string accepted by httpx (optional)
    """
    http_client = config.get("HTTP_CLIENT", {})
    verify_ssl = http_client.get("VERIFY_SSL", True)
    ca_bundle = http_client.get("CA_BUNDLE")  # e.g., "C:/company/ca.pem" or "/etc/ssl/certs/corp-ca.pem"
    proxies = http_client.get("PROXIES")      # e.g., {"http": "http://user:pass@proxy:8080", "https": "..."} or "http://..."

    # If a CA bundle path is provided, use it for verification.
    # Otherwise, use the VERIFY_SSL boolean flag.
    verify: Any = ca_bundle if ca_bundle else verify_ssl
    kwargs: Dict[str, Any] = {"verify": verify}
    if proxies:
        kwargs["proxies"] = proxies
    return kwargs
# --- END CONFIGURATION HELPERS ---

# - Helper Function for Filename Sanitization -
def sanitize_filename(name: str) -> str:
    """Cleans a string to be a valid filename."""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s-]', '_', name).strip()
    name = re.sub(r'\s+', '_', name)
    return name

# --- Core Fetching & Parsing Functions ---

async def fetch_url(client: httpx.AsyncClient, url: str, config: Dict) -> str:
    """Fetches content from a URL using the 'Perfect Disguise' browser headers
    from the configuration file for maximum compatibility."""
    logging.info(f"Fetching URL: {url}")
    headers = config.get("HTTP_HEADERS", {})
    if not headers:
        logging.warning("HTTP_HEADERS not found in config.json. Using a basic User-Agent.")
        headers = {'User-Agent': 'Mozilla/5.0'}
    timeout = config.get("HTTP_CLIENT", {}).get("REQUEST_TIMEOUT", 30.0)
    try:
        # Use the client passed in, which has proxy/CA settings
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

async def prefetch_source(client: httpx.AsyncClient, site: Dict[str, Any], config: Dict, today_str: str) -> bool:
    """Fetches and saves a single data source to the input directory."""
    input_dir = Path(config["INPUT_DIR"])
    input_dir.mkdir(exist_ok=True, parents=True)
    url = site["url"].format(date_str_iso=today_str)

    # Add a print statement for user feedback
    print(f"    -> Prefetching: {site['name']}")
    logging.info(f"Prefetching: {site['name']}")
    content = await fetch_url(client, url, config) # Pass client with settings
    if content:
        filename = sanitize_filename(site['name']) + ".html"
        output_path = input_dir / filename
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logging.info(f"[SUCCESS] Saved '{site['name']}' to {output_path}")
            return True
        except Exception as e:
            logging.error(f"[ERROR] Failed to write file for '{site['name']}': {e}")
    return False

async def run_batch_prefetch(config: Dict):
    """Automatically downloads all enabled data sources to the input folder."""
    logging.info("Starting Automated Pre-Fetch of Enabled Sources...")
    today_str = date.today().strftime("%Y-%m-%d")
    SKIP_LIST = ["(DISABLED)", "IGNORE", "SKIP"]

    # Get a list of all modern adapter source IDs once to avoid re-importing in the loop
    adapter_source_ids = list(config.get("DATA_SOURCES_V2", {}).keys())
    logging.info(f"Found {len(adapter_source_ids)} modern adapters. Will skip pre-fetching for these sources.")

    # --- Use the helper to create the client with proxy/CA settings ---
    async with httpx.AsyncClient(follow_redirects=True, **build_httpx_client_kwargs(config)) as client:
        prefetch_tasks = []
        for category in config.get("DATA_SOURCES", []):
            logging.info(f"- Processing Category: {category['title']} -")
            sites = [site for site in category.get("sites", []) if site.get("enabled", True)]

            for site in sites:
                site_name = site.get("name", "")
                if any(skip_item in site_name for skip_item in SKIP_LIST):
                    logging.info(f"--> Skipping '{site_name}' (on hard-coded skip list).")
                    continue

                # Skip if a V2 adapter exists for this source
                if any(adapter_id in site_name.lower() for adapter_id in adapter_source_ids):
                    logging.info(f"--> Skipping '{site_name}' (handled by modern V2 adapter).")
                    continue

                if site.get("url"):
                    task = asyncio.create_task(prefetch_source(client, site, config, today_str))
                    prefetch_tasks.append(task)

        results = await asyncio.gather(*prefetch_tasks)
        success_count = sum(1 for r in results if r)
        logging.info("-" * 50)
        logging.info(f"Automated Pre-Fetch Complete. Successfully downloaded {success_count} of {len(prefetch_tasks)} sources.")
        logging.info(f"Files are located in the '{config['INPUT_DIR']}' directory.")
        logging.info("You can now run the 'Parse Local Files' option from the main menu.")
        logging.info("-" * 50)

# --- Connection Testing Logic ---

async def test_scanner_connections(config: Dict):
    """Tests all enabled scanner connections to ensure URLs are reachable."""
    logging.info("Testing all enabled data source connections...")
    today_str = date.today().strftime("%Y-%m-%d")
    headers = config.get("HTTP_HEADERS", {})

    # --- Use the helper to create the client with proxy/CA settings ---
    async with httpx.AsyncClient(headers=headers, **build_httpx_client_kwargs(config)) as client:
        for category in config.get("DATA_SOURCES", []):
            logging.info(f"- Testing Category: {category['title']} -")
            sites = [site for site in category.get("sites", []) if site.get("enabled", True)]
            for site in sites:
                if site.get("url"):
                    url = site["url"].format(date_str_iso=today_str)
                    try:
                        # Use a streaming GET request to test connection, as HEAD is often blocked.
                        async with client.stream("GET", url, timeout=15.0, follow_redirects=True) as response:
                            # We don't need to read the body, just establishing the connection
                            # and getting the status code is enough for a test.
                            status_code = response.status_code

                        if 200 <= status_code < 400:
                            logging.info(f"[SUCCESS] ({status_code}) - {site['name']}")
                        else:
                            logging.warning(f"[WARNING] ({status_code}) - {site['name']} at {url}")
                    except httpx.RequestError as e:
                        logging.error(f"[ERROR] FAILED - {site['name']} at {url} ({type(e).__name__})")

# This file is now focused on V1 data collection (prefetch) and connection testing.
# The V1 "Quick Strike" scanner has been deprecated in favor of the unified V2 pipeline.




# --- Main Execution Guard ---
if __name__ == "__main__":
    # This allows running the scanner directly for testing
    config = load_config()
    if not config:
        sys.exit(1)
    # Force logging to stdout for this script
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    # Running the batch prefetch by default for this test.
    asyncio.run(run_batch_prefetch(config))
