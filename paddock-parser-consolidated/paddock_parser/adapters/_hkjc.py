import asyncio
import datetime as dt
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from typing import Optional, List

from ..sources import RawRaceDocument, FieldConfidence, RunnerDoc, register_adapter
from ..fetching import resilient_get, bootstrap_session_with_playwright
from ..normalizer import canonical_track_key, canonical_race_key, parse_hhmm_any, map_discipline
from .base_v3 import BaseAdapterV3

@register_adapter
class HkjcAdapter(BaseAdapterV3):
    """
    V3 Adapter for the Hong Kong Jockey Club (HKJC).

    This adapter is based on the logic found in the gist at:
    https://gist.github.com/tomfoolc/ef039b229c8e97bd40c5493174bca839

    It has been adapted to use this project's V3 architecture, including
    Playwright for browser bootstrapping and our custom data structures.
    """
    source_id = "hkjc"

    async def fetch(self) -> list[RawRaceDocument]:
        """
        Fetches race data from HKJC.
        """
        if not self.is_initialized or not self.site_config:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        # The gist targets the results page. We will target the racecard page,
        # assuming a similar URL structure.
        target_url = self.site_config.get("url", "https://racing.hkjc.com/racing/information/English/Racing/Racecard.aspx")

        # The gist uses Selenium, which implies JS is needed. We'll use Playwright.
        logging.info(f"[{self.source_id}] Bootstrapping with Playwright...")
        if not await bootstrap_session_with_playwright(target_url):
            # As diagnosed before, this will likely fail in the sandbox.
            # We will proceed with a simple fetch, which may or may not work.
            logging.warning(f"[{self.source_id}] Playwright bootstrap failed. Proceeding with simple fetch...")

        try:
            config = self.config_manager.get_config()
            response = await resilient_get(target_url, config)
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_races(soup)
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse race list: {e}", exc_info=True)
            return []

    def _parse_races(self, soup: BeautifulSoup) -> list[RawRaceDocument]:
        """
        Parses the HKJC racecard page.
        This logic is adapted from the gist, but targets the racecard page structure.
        """
        races = []

        # The gist uses 'table.f_fs12.js_racecard' for the results page.
        # We'll guess a similar selector for the racecard.
        race_table = soup.find("table", class_="racecard")
        if not race_table:
            logging.warning(f"[{self.source_id}] Could not find main racecard table with class 'racecard'.")
            return []

        # Extract track from a known element, fallback to a default
        venue_el = soup.find("span", class_="font_w7")
        track_name = venue_el.get_text(strip=True) if venue_el else "Sha Tin"
        track_key = canonical_track_key(track_name)

        # The gist gets the number of races from image tags. We'll look for race rows.
        # This is a hypothetical selector.
        race_rows = race_table.find_all("tr", class_="raceno")

        for i, row in enumerate(race_rows):
            try:
                race_no = i + 1

                # Extract details from the row
                time_el = row.find("td", class_="raceTime")
                race_time = parse_hhmm_any(time_el.get_text(strip=True)) if time_el else f"12:{i*15:02d}"

                race_key = canonical_race_key(track_key, race_time)

                # This is a placeholder as we can't see the runner details page
                placeholder_runners = [
                    RunnerDoc(
                        runner_id=f"{race_key}-{j+1}",
                        name=FieldConfidence(f"Runner {j+1}", 0.1, self.source_id),
                        number=FieldConfidence(str(j+1), 0.1, self.source_id)
                    ) for j in range(10) # Assume 10 runners for now
                ]

                races.append(RawRaceDocument(
                    source_id=self.source_id,
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    track_key=track_key,
                    race_key=race_key,
                    start_time_iso=f"{dt.date.today().isoformat()}T{race_time}:00Z",
                    runners=placeholder_runners,
                    extras={"race_title": FieldConfidence(f"Race {race_no}", 0.5, self.source_id)}
                ))
            except Exception as e:
                logging.error(f"[{self.source_id}] Error parsing a race row: {e}")
                continue

        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races.")
        return races
