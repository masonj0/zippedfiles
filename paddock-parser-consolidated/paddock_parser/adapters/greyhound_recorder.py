import asyncio
import datetime as dt
import logging
import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from typing import Optional, List

from ..sources import RawRaceDocument, FieldConfidence, RunnerDoc, register_adapter
from ..fetching import resilient_get
from ..normalizer import canonical_track_key, canonical_race_key, parse_hhmm_any, map_discipline, normalize_race_docs, NormalizedRace
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
            logging.error(f"[{self.source_id}] Failed to fetch or parse race list: {e}", exc_info=True)
            return []

    def _parse_races_from_html(self, soup: BeautifulSoup) -> list[RawRaceDocument]:
        """
        Parses the race data from the HTML structure of the racecard page.
        """
        races = []

        course_name_tag = soup.find("a", class_="RC-courseTime__link")
        course_name = course_name_tag.get_text(strip=True) if course_name_tag else "Unknown Course"
        track_key = canonical_track_key(course_name.replace("(IRE)","").strip())

        race_divs = soup.find_all("div", class_="RC-meetingDay__race")

        if not race_divs:
            logging.error(f"[{self.source_id}] No race divs found on the page.")
            return []

        for race_div in race_divs:
            try:
                race_time_tag = race_div.find("span", class_="RC-meetingDay__raceTime")
                race_time_str = race_time_tag.get_text(strip=True) if race_time_tag else ""
                race_time = parse_hhmm_any(race_time_str)
                if not race_time:
                    continue

                race_key = canonical_race_key(track_key, race_time)
                race_title_tag = race_div.find("a", class_="RC-meetingDay__raceTitle")
                race_title = race_title_tag.get_text(strip=True) if race_title_tag else ""
                race_url = urljoin(self.base_url, race_title_tag['href']) if race_title_tag and 'href' in race_title_tag.attrs else ""

                runners = []
                runner_rows = race_div.find_all("div", class_="RC-runnerRow")
                for runner_row in runner_rows:
                    if 'js-runnerNonRunner' in runner_row.get('class', []):
                        continue

                    runner_name_tag = runner_row.find("a", class_="RC-runnerName")
                    runner_name = runner_name_tag.get_text(strip=True) if runner_name_tag else ""

                    number_tag = runner_row.find("span", class_="RC-runnerNumber__no")
                    number = number_tag.get_text(strip=True) if number_tag else ""

                    jockey_tag = runner_row.find("a", attrs={"data-test-selector": "RC-cardPage-runnerJockey-name"})
                    jockey = jockey_tag.get_text(strip=True) if jockey_tag else ""

                    trainer_tag = runner_row.find("a", attrs={"data-test-selector": "RC-cardPage-runnerTrainer-name"})
                    trainer = trainer_tag.get_text(strip=True) if trainer_tag else ""

                    runners.append(RunnerDoc(
                        runner_id=f"{race_key}-{number}",
                        name=FieldConfidence(runner_name, 0.9, self.source_id),
                        number=FieldConfidence(number, 0.9, self.source_id),
                        jockey=FieldConfidence(jockey, 0.9, self.source_id),
                        trainer=FieldConfidence(trainer, 0.9, self.source_id),
                        odds=None
                    ))

                if not runners:
                    continue

                races.append(RawRaceDocument(
                    source_id=self.source_id,
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    track_key=track_key,
                    race_key=race_key,
                    start_time_iso=f"{dt.date.today().isoformat()}T{race_time}:00Z",
                    runners=runners,
                    extras={
                        "race_title": FieldConfidence(race_title, 0.9, self.source_id),
                        "race_url": FieldConfidence(race_url, 0.9, self.source_id)
                    }
                ))
            except Exception as e:
                logging.warning(f"[{self.source_id}] Failed to parse a race entry from HTML: {e}")
                continue

        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races from HTML.")
        return races

    def _parse_and_normalize_racecard(self, html_content: str) -> list[NormalizedRace]:
        """
        Parses the HTML content and returns a list of fully normalized races.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        raw_races = self._parse_races_from_html(soup)

        normalized_races = [normalize_race_docs(raw_race) for raw_race in raw_races]

        return normalized_races
