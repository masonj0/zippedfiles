#!/usr/bin/env python3
"""
Paddock Parser Toolkit - RSS Goldmine Discovery Tool

This script probes a list of websites for common RSS/XML feed URLs.
It's a utility for developers to discover new, structured data sources that
can be used to create new adapters.
"""

import asyncio
import httpx
from typing import Set

# --- Configuration ---
# A list of base URLs to check for feeds.
# In a more advanced version, this could be read from a file or config.
BASE_URLS = [
    "https://www.timeform.com",
    "https://www.racingpost.com",
    "https://www.attheraces.com",
    "https://www.sportinglife.com",
    "https://www.equibase.com",
]

# Common paths where RSS/XML feeds are often found.
FEED_PATHS = [
    "/rss",
    "/feed",
    "/rss.xml",
    "/feed.xml",
    "/index.xml",
    "/sitemap.xml",
]


async def check_url(client: httpx.AsyncClient, url: str) -> str | None:
    """
    Checks a single URL to see if it appears to be a valid RSS/XML feed.
    Returns the URL if it's a likely feed, otherwise None.
    """
    try:
        response = await client.get(url, timeout=10, follow_redirects=True)

        # Check 1: Successful status code
        if response.status_code != 200:
            return None

        # Check 2: Content-Type header
        content_type = response.headers.get("content-type", "").lower()
        is_xml_type = "xml" in content_type or "rss" in content_type

        # Check 3: Content sniffing
        content_start = response.text[:100].lower()
        is_xml_content = "<rss" in content_start or "<?xml" in content_start

        if is_xml_type or is_xml_content:
            print(f"[+] Found potential feed: {url}")
            return str(response.url)  # Return the final URL after redirects

    except httpx.RequestError:
        # Don't log errors for timeouts, connection errors, etc. as many will be 404s.
        pass
    except Exception as e:
        print(f"[!] Error checking {url}: {e}")

    return None


async def main():
    """Main asynchronous function to run the discovery tool."""
    print("--- RSS Goldmine Discovery Tool ---")
    print(f"Probing {len(BASE_URLS)} websites for {len(FEED_PATHS)} common feed paths each...")

    found_feeds: Set[str] = set()

    async with httpx.AsyncClient() as client:
        tasks = []
        for base_url in BASE_URLS:
            for path in FEED_PATHS:
                url_to_check = f"{base_url.rstrip('/')}{path}"
                tasks.append(check_url(client, url_to_check))

        results = await asyncio.gather(*tasks)

        for feed_url in results:
            if feed_url:
                found_feeds.add(feed_url)

    print("\n--- Discovery Complete ---")
    if found_feeds:
        print(f"Found {len(found_feeds)} unique feed(s):")
        for feed in sorted(list(found_feeds)):
            print(f"  - {feed}")
    else:
        print("No RSS or XML feeds were discovered with the common paths.")


if __name__ == "__main__":
    asyncio.run(main())
