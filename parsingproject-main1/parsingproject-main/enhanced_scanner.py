#!/usr/bin/env python3
"""Paddock Parser Toolkit - Enhanced Scanner & Prefetcher Module"""
import sys
import asyncio
import argparse
import httpx
import json
import logging
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup
import re
import unicodedata
import hashlib

from paddock_parser.config import load_config
from paddock_parser.normalizer import normalize_course_name, parse_hhmm_any, convert_odds_to_fractional_decimal, map_discipline
from paddock_parser.sources import ADAPTERS

# --- CONFIGURATION HELPERS ---
def build_httpx_client_kwargs(config: Dict) -> Dict[str, Any]:
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
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s-]', '_', name).strip()
    name = re.sub(r'\s+', '_', name)
    return name

# --- Core Fetching & Parsing Functions ---
async def fetch_url(client: httpx.AsyncClient, url: str, config: Dict) -> str:
    logging.info(f"Fetching URL: {url}")
    headers = config.get("HTTP_HEADERS", {})
    if not headers:
        logging.warning("HTTP_HEADERS not found in config.json. Using a basic User-Agent.")
        headers = {'User-Agent': 'Mozilla/5.0'}
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
async def prefetch_source(client: httpx.AsyncClient, site: Dict[str, Any], config: Dict, today_str: str) -> bool:
    input_dir = Path(config["INPUT_DIR"])
    input_dir.mkdir(exist_ok=True, parents=True)
    url = site["url"].format(date_str_iso=today_str)

    print(f"    -> Prefetching: {site['name']}")
    logging.info(f"Prefetching: {site['name']}")
    content = await fetch_url(client, url, config)
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
    logging.info("Starting Automated Pre-Fetch of Enabled Sources...")
    today_str = date.today().strftime("%Y-%m-%d")
    SKIP_LIST = ["(DISABLED)", "IGNORE", "SKIP"]

    adapter_source_ids = [adapter.source_id for adapter in ADAPTERS]
    logging.info(f"Found {len(adapter_source_ids)} modern adapters. Will skip pre-fetching for these sources.")

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
    logging.info("Testing all enabled data source connections...")
    today_str = date.today().strftime("%Y-%m-%d")
    headers = config.get("HTTP_HEADERS", {})

    async with httpx.AsyncClient(headers=headers, **build_httpx_client_kwargs(config)) as client:
        for category in config.get("DATA_SOURCES", []):
            logging.info(f"- Testing Category: {category['title']} -")
            sites = [site for site in category.get("sites", []) if site.get("enabled", True)]
            for site in sites:
                if site.get("url"):
                    url = site["url"].format(date_str_iso=today_str)
                    try:
                        async with client.stream("GET", url, timeout=15.0, follow_redirects=True) as response:
                            status_code = response.status_code

                        if 200 <= status_code < 400:
                            logging.info(f"[SUCCESS] ({status_code}) - {site['name']}")
                        else:
                            logging.warning(f"[WARNING] ({status_code}) - {site['name']} at {url}")
                    except httpx.RequestError as e:
                        logging.error(f"[ERROR] FAILED - {site['name']} at {url} ({type(e).__name__})")

# --- Main Execution Guard ---
if __name__ == "__main__":
    config = load_config()
    if not config:
        sys.exit(1)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    asyncio.run(run_batch_prefetch(config))
