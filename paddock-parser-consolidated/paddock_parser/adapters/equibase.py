import asyncio
import datetime as dt
import logging
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from typing import Optional

from .base_v3 import BaseAdapterV3
from ..fetching import resilient_get
from ..normalizer import NormalizedRace, NormalizedRunner, canonical_track_key, canonical_race_key
from ..sources import RawRaceDocument, register_adapter
from ..config_manager import config_manager
from ..utils import remove_honeypot_links

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
        soup = remove_honeypot_links(soup)
        links = soup.select('a[href*="/static/entry/"][href*="USA-D.html"]')

        race_urls = {urljoin(self._base_url, a['href']) for a in links}

        logging.info(f"Found {len(race_urls)} unique links matching the pattern.")
        return sorted(list(race_urls))

    def _parse_racecard(self, html_content: str) -> list[NormalizedRace]:
        """
        Parses the HTML content of a race card summary page to extract race information.

        Note: This parser is designed for the main entries page (e.g., SAR082225USA-EQB.html),
        which lists all races for a day. It does not parse the detailed page for a single
        race, so runner information (jockeys, trainers) is not available here.
        """
        races = []
        soup = BeautifulSoup(html_content, 'html.parser')

        track_name_elem = soup.find('h1', id='pageHeader')
        track_name = track_name_elem.text.strip().replace(" Entries", "") if track_name_elem else "Unknown Track"
        track_key = canonical_track_key(track_name)

        date_elem = soup.find('h1', id='pageHeaderMobile')
        if date_elem:
            date_str = date_elem.text.split('|')[1].strip()
            race_date = dt.datetime.strptime(date_str, '%b %d, %Y').date()
        else:
            race_date = dt.date.today()

        race_table = soup.find('table', id='entryRaces')
        if not race_table:
            logging.warning("Could not find race table with id 'entryRaces'")
            return []

        for row in race_table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 7:
                continue

            try:
                race_number = int(cells[0].text.strip())
                post_time_str = cells[6].text.strip().replace(" ET", "")
                post_time = dt.datetime.strptime(post_time_str, '%I:%M %p').time()

                start_datetime = dt.datetime.combine(race_date, post_time)
                start_time_iso = start_datetime.isoformat()

                race_time_for_key = post_time.strftime('%H%M')
                race_key = canonical_race_key(track_key, race_time_for_key)

                race = NormalizedRace(
                    race_key=race_key,
                    track_key=track_key,
                    start_time_iso=start_time_iso,
                    race_name=cells[2].text.strip(),
                    runners=[],
                    source_ids=[self.source_id],
                    extras={
                        "race_number": race_number,
                        "purse": cells[1].text.strip(),
                        "distance": cells[3].text.strip(),
                        "surface": cells[4].text.strip(),
                        "starters": int(cells[5].text.strip())
                    }
                )
                races.append(race)
            except (ValueError, IndexError) as e:
                logging.error(f"Could not parse race row: {row}. Error: {e}")
                continue

        return races
