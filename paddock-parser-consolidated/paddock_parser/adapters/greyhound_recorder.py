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
        Parses the race data from a JSON object embedded in the HTML.
        """
        races = []
        script_tag = soup.find("script", type="application/ld+json")
        if not script_tag:
            logging.error(f"[{self.source_id}] Could not find JSON-LD script tag.")
            return []

        try:
            json_data = json.loads(script_tag.string)
            for event in json_data.get("event", []):
                track_key = canonical_track_key(event.get("location", {}).get("name"))
                race_key = canonical_race_key(track_key, event.get("startDate"))
                runners = []
                for competitor in event.get("competitor", []):
                    runners.append(
                        RunnerDoc(
                            runner_id=f"{race_key}-{competitor.get('identifier')}",
                            name=FieldConfidence(competitor.get("name"), 0.9, self.source_id),
                            number=FieldConfidence(
                                competitor.get("identifier"), 0.9, self.source_id
                            ),
                        )
                    )
                if not runners:
                    continue

                races.append(
                    RawRaceDocument(
                        source_id=self.source_id,
                        fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        track_key=track_key,
                        race_key=race_key,
                        start_time_iso=event.get("startDate"),
                        runners=runners,
                    )
                )
        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"[{self.source_id}] Failed to parse JSON-LD data: {e}", exc_info=True)
            return []

        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races from JSON-LD.")
        return races

    def _parse_and_normalize_racecard(self, html_content: str) -> list[NormalizedRace]:
        """
        Parses the HTML content and returns a list of fully normalized races.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        raw_races = self._parse_races_from_html(soup)

        normalized_races = [normalize_race_docs(raw_race) for raw_race in raw_races]

        return normalized_races
