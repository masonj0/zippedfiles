import asyncio
import datetime as dt
import logging
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from typing import Optional

from .base_v3 import BaseAdapterV3
from ..fetching import resilient_get
from ..normalizer import NormalizedRace
from ..sources import RawRaceDocument, register_adapter
from ..config_manager import config_manager

print("--- [equibase.py] Module loaded ---", file=sys.stderr)

@register_adapter
class EquibaseAdapter(BaseAdapterV3):
    """
    Adapter for fetching racecards from Equibase.
    """
    source_id = "equibase"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_url = "https://www.equibase.com"
        self._entries_url = "https://www.equibase.com/static/entry/index.html"
        print(f"--- [EquibaseAdapter] __init__ called for {self.source_id} ---", file=sys.stderr)
        logging.info(f"--- [EquibaseAdapter] __init__ called for {self.source_id} ---")


    def initialize(self) -> bool:
        print(f"--- [EquibaseAdapter] initialize called for {self.source_id} ---", file=sys.stderr)
        logging.info(f"--- [EquibaseAdapter] initialize called for {self.source_id} ---")
        initialized = super().initialize()
        print(f"--- [EquibaseAdapter] super().initialize() returned: {initialized} ---", file=sys.stderr)
        logging.info(f"--- [EquibaseAdapter] super().initialize() returned: {initialized} ---")
        return initialized

    async def fetch(self) -> list[RawRaceDocument]:
        logging.info(f"[{self.source_id}] Starting fetch...")
        if not self.is_initialized:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        try:
            logging.info(f"[{self.source_id}] Fetching entries from {self._entries_url}")

            config = config_manager.get_config()
            list_response = await resilient_get(self._entries_url, extra_headers=config.get('StealthHeaders'))

            if not list_response or not list_response.text:
                logging.error(f"[{self.source_id}] Failed to retrieve content from {self._entries_url}")
                return []

            race_urls = self._parse_race_list(list_response.text)
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse race list: {e}", exc_info=True)
            return []

        logging.info(f"[{self.source_id}] Found {len(race_urls)} race URLs to process.")

        if race_urls:
            logging.info(f"[{self.source_id}] Successfully fetched race list. URLs found: {race_urls[:5]}")

        return []

    def _parse_race_list(self, html_content: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        links = soup.select('a[href*="/static/entry/"][href*="USA-D.html"]')

        race_urls = {urljoin(self._base_url, a['href']) for a in links}

        logging.info(f"Found {len(race_urls)} unique links matching the pattern.")
        return sorted(list(race_urls))
