import datetime as dt
import logging
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from typing import Optional

from .base_v3 import BaseAdapterV3
from ..fetching import resilient_get, bootstrap_session_with_playwright
from ..normalizer import canonical_track_key, canonical_race_key
from ..sources import (
    FieldConfidence,
    RawRaceDocument,
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

        tasks = [self._fetch_and_parse_race(url) for url in race_urls]
        results = await asyncio.gather(*tasks)
        return [doc for doc in results if doc]

    async def _fetch_and_parse_race(self, url: str) -> Optional[RawRaceDocument]:
        """Fetches an individual race page and parses its details."""
        try:
            config = self.config_manager.get_config()
            response = await resilient_get(url, config)
            soup = BeautifulSoup(response.text, "html.parser")

            path_parts = urlparse(url).path.strip('/').split('/')
            track_name = path_parts[2].replace('-', ' ')
            track_key = canonical_track_key(track_name)
            time_str = path_parts[4]
            race_date = path_parts[3]
            race_key = canonical_race_key(track_key, time_str)

            runners = self._parse_race_details(soup, race_key)

            return RawRaceDocument(
                source_id=self.source_id,
                fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                track_key=track_key,
                race_key=race_key,
                start_time_iso=f"{race_date}T{time_str[:2]}:{time_str[2:]}:00Z",
                runners=runners,
                extras={"race_url": FieldConfidence(url, 0.95, "parsed_from_detail")}
            )
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse race details for URL {url}: {e}")
            return None

    def _parse_race_list(self, html_content: str) -> list[str]:
        """
        Parses the main racecards page to find links to individual race pages.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        race_links = {
            urljoin(self._base_url, a['href'])
            for a in soup.select("a.rp-racecard-race-link")
        }
        return list(race_links)

    def _parse_race_details(self, soup: BeautifulSoup, race_key: str) -> list:
        """Parses the runners from a Timeform race detail page."""
        runners = []
        # This selector targets the rows in the main racecard table
        runner_rows = soup.select("div.rp-racecard-runner-row")
        for row in runner_rows:
            try:
                saddle_cloth_el = row.select_one(".rp-racecard-runner-saddle-cloth")
                horse_name_el = row.select_one(".rp-racecard-runner-horse-name")
                jockey_name_el = row.select_one(".rp-racecard-runner-jockey-name")
                trainer_name_el = row.select_one(".rp-racecard-runner-trainer-name")
                odds_el = row.select_one(".rp-racecard-runner-odds .rp-price-button__price")

                if not all([saddle_cloth_el, horse_name_el]):
                    continue

                saddle_cloth = saddle_cloth_el.get_text(strip=True)
                horse_name = horse_name_el.get_text(strip=True)

                runners.append({
                    "runner_id": f"{race_key}-{saddle_cloth}",
                    "name": FieldConfidence(horse_name, 0.9, "parsed_from_detail"),
                    "number": FieldConfidence(saddle_cloth, 0.9, "parsed_from_detail"),
                    "jockey": FieldConfidence(jockey_name_el.get_text(strip=True), 0.9, "parsed_from_detail") if jockey_name_el else None,
                    "trainer": FieldConfidence(trainer_name_el.get_text(strip=True), 0.9, "parsed_from_detail") if trainer_name_el else None,
                    "odds": FieldConfidence(odds_el.get_text(strip=True), 0.9, "parsed_from_detail") if odds_el else None,
                    "extras": {}
                })
            except Exception as e:
                logging.warning(f"[{self.source_id}] Could not parse a runner row: {e}")
                continue
        return runners
