import asyncio
import datetime as dt
import logging
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from typing import Optional

from adapters.base_v3 import BaseAdapterV3
from fetching import resilient_get, bootstrap_session_with_playwright
from normalizer import canonical_track_key, canonical_race_key, normalize_course_name
from sources import (
    FieldConfidence,
    RawRaceDocument,
    RunnerDoc,
    register_adapter,
)

@register_adapter
class TimeformAdapter(BaseAdapterV3):
    """
    V3 Adapter for Timeform.
    This adapter uses a Playwright bootstrap to handle anti-bot challenges
    before fetching data with a standard HTTP client.
    """
    source_id = "timeform"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_url: str = ""

    def initialize(self) -> bool:
        """
        Initializes the adapter by setting the base URL from the config.
        """
        if not super().initialize():
            return False

        self._base_url = self.site_config.get("base_url", "https://www.timeform.com")
        return True

    async def fetch(self) -> list[RawRaceDocument]:
        """
        Fetches race data from Timeform.
        """
        if not self.is_initialized or not self.site_config:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        target_url = self.site_config.get("url")
        if not target_url:
            logging.error(f"[{self.source_id}] URL not configured.")
            return []

        # Use Playwright to solve challenges and get cookies
        wait_selector = ".w-racecard-grid-meeting"
        if not await bootstrap_session_with_playwright(target_url, wait_selector):
            logging.error(f"[{self.source_id}] Playwright bootstrap failed. Aborting fetch.")
            return []

        # Now fetch the main page using the session with cookies
        try:
            config = self.config_manager.get_config()
            list_response = await resilient_get(target_url, config)
            race_urls = self._parse_race_list(list_response.text)
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse race list: {e}")
            return []

        logging.info(f"[{self.source_id}] Found {len(race_urls)} race URLs to process.")

        # This part can be expanded to fetch details for each race URL
        # For now, we return a raw document for each URL found
        race_docs = [self._create_raw_doc_from_url(url) for url in race_urls]
        return [doc for doc in race_docs if doc]

    def _parse_race_list(self, html_content: str) -> list[str]:
        """
        Parses the main racecards page to find links to individual race pages.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        race_links = {
            urljoin(self._base_url, a['href'])
            for a in soup.find_all("a", href=True)
            if a['href'] and a['href'].startswith('/horse-racing/racecards/')
        }
        return list(race_links)

    def _create_raw_doc_from_url(self, url: str) -> Optional[RawRaceDocument]:
        """
        Creates a placeholder RawRaceDocument from a race URL.
        In a full implementation, this would also fetch and parse the race details.
        """
        try:
            path_parts = urlparse(url).path.strip('/').split('/')
            track_name = path_parts[2].replace('-', ' ')
            track_key = canonical_track_key(track_name)
            time_str = path_parts[4]
            race_date = path_parts[3]

            return RawRaceDocument(
                source_id=self.source_id,
                fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                track_key=track_key,
                race_key=canonical_race_key(track_key, time_str),
                start_time_iso=f"{race_date}T{time_str[:2]}:{time_str[2:]}:00Z",
                runners=[], # Placeholder
                extras={"race_url": FieldConfidence(url, 0.95, "parsed_from_list")}
            )
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to create raw doc from URL {url}: {e}")
            return None
