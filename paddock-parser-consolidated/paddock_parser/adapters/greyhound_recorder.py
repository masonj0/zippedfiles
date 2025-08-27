import datetime as dt
import json
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..sources import RawRaceDocument, FieldConfidence, RunnerDoc, register_adapter
from ..fetching import resilient_get
from ..normalizer import (
    canonical_track_key,
    canonical_race_key,
    parse_hhmm_any,
    normalize_race_docs,
    NormalizedRace,
)
from ..utils import remove_honeypot_links
from .base_v3 import BaseAdapterV3


@register_adapter
class GreyhoundRecorderAdapter(BaseAdapterV3):
    """
    V3 Adapter for thegreyhoundrecorder.com.au.

    This adapter scrapes the racecard page by finding a JSON object embedded
    in the HTML, which contains all the necessary data. This approach is
    based on the methodology from the `joenano/rpscrape` project.
    """

    source_id = "greyhound_recorder"
    base_url = "https://www.thegreyhoundrecorder.com.au"

    async def fetch(self) -> list[RawRaceDocument]:
        """
        Fetches race data from The Greyhound Recorder.
        """
        if not self.is_initialized or not self.site_config:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        target_url = f"{self.base_url}/form-guides"

        try:
            config = self.config_manager.get_config()
            # Correctly pass the headers dictionary, not the whole config
            headers = config.get("StealthHeaders")
            response = await resilient_get(target_url, extra_headers=headers)

            if not response:
                logging.error(f"[{self.source_id}] No response received from {target_url}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            soup = remove_honeypot_links(soup)
            return self._parse_races_from_html(soup)
        except Exception as e:
            logging.error(
                f"[{self.source_id}] Failed to fetch or parse race list: {e}", exc_info=True
            )
            return []

    def _parse_races_from_html(self, soup: BeautifulSoup) -> list[RawRaceDocument]:
        """
        Parses the race data from the HTML structure of the long-form racecard page.
        """
        races = []

        try:
            track_name_tag = soup.find("h1", class_="form-guide-meeting__heading")
            if not track_name_tag:
                logging.error(f"[{self.source_id}] Could not find track name tag.")
                return []

            track_name_full = track_name_tag.get_text(strip=True)
            track_name = track_name_full.split('(')[0].strip()
            track_key = canonical_track_key(track_name)

            race_header = soup.find("div", class_="meeting-event__header--desktop")
            if not race_header:
                logging.error(f"[{self.source_id}] Could not find race header.")
                return []

            race_time_tag = race_header.find("div", class_="meeting-event__header-time")
            race_time_str = race_time_tag.get_text(strip=True) if race_time_tag else ""

            race_time = parse_hhmm_any(race_time_str)
            if not race_time:
                logging.warning(f"[{self.source_id}] Could not parse race time: {race_time_str}")
                return []

            race_key = canonical_race_key(track_key, race_time)

            runners = []
            runner_rows = soup.select("tr.form-guide-long-form-table-selection")

            for runner_row in runner_rows:
                if "form-guide-long-form-table-selection--scratched" in runner_row.get("class", []):
                    continue

                runner_name_tag = runner_row.find("span", class_="form-guide-long-form-table-selection__name")
                runner_name = runner_name_tag.get_text(strip=True) if runner_name_tag else ""

                rug_img_tag = runner_row.find("img", class_="form-guide-long-form-table-selection__rug")
                number_str = ""
                if rug_img_tag and rug_img_tag.get('alt'):
                    number_str = rug_img_tag.get('alt').replace("Rug ", "").strip()

                if not runner_name or not number_str:
                    continue

                runners.append(
                    RunnerDoc(
                        runner_id=f"{race_key}-{number_str}",
                        name=FieldConfidence(runner_name, 0.9, self.source_id),
                        number=FieldConfidence(number_str, 0.9, self.source_id),
                    )
                )

            if not runners:
                logging.warning(f"[{self.source_id}] No runners found for race {race_key}")
                return []

            start_time_iso = f"{dt.date.today().isoformat()}T{race_time}:00Z"

            # There are multiple ld+json scripts, find the SportsEvent one
            for script_tag in soup.find_all("script", type="application/ld+json"):
                try:
                    json_data = json.loads(script_tag.string)
                    if json_data.get("@type") == "SportsEvent" and json_data.get("startDate"):
                        start_time_iso = json_data.get("startDate")
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

            races.append(
                RawRaceDocument(
                    source_id=self.source_id,
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    track_key=track_key,
                    race_key=race_key,
                    start_time_iso=start_time_iso,
                    runners=runners,
                )
            )
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to parse race from HTML: {e}", exc_info=True)
            return []

        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races from HTML.")
        return races

    def _parse_and_normalize_racecard(self, html_content: str) -> list[NormalizedRace]:
        """
        Parses the HTML content and returns a list of fully normalized races.
        """
        soup = BeautifulSoup(html_content, "lxml")
        raw_races = self._parse_races_from_html(soup)

        normalized_races = [normalize_race_docs(raw_race) for raw_race in raw_races]

        return normalized_races
