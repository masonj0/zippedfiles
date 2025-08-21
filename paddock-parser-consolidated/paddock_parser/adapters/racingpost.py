import asyncio
import datetime as dt
import logging
import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from typing import Optional, List

from ..sources import RawRaceDocument, FieldConfidence, RunnerDoc, register_adapter
from ..fetching import resilient_get
from ..normalizer import canonical_track_key, canonical_race_key, parse_hhmm_any, map_discipline
from .base_v3 import BaseAdapterV3

@register_adapter
class RacingPostAdapter(BaseAdapterV3):
    """
    V3 Adapter for racingpost.com.

    This adapter scrapes the racecard page by finding a JSON object embedded
    in the HTML, which contains all the necessary data. This approach is
    based on the methodology from the `joenano/rpscrape` project.
    """
    source_id = "racingpost"
    base_url = "https://www.racingpost.com"

    async def fetch(self) -> list[RawRaceDocument]:
        """
        Fetches race data from Racing Post.
        """
        if not self.is_initialized or not self.site_config:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        # The __NEXT_DATA__ object is on the main racecards page, not the API endpoint from the config.
        target_url = f"{self.base_url}/racecards"

        try:
            config = self.config_manager.get_config()
            response = await resilient_get(target_url, config)
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_races_from_json(soup)
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse race list: {e}", exc_info=True)
            return []

    def _parse_races_from_json(self, soup: BeautifulSoup) -> list[RawRaceDocument]:
        """
        Parses the embedded JSON data from the __NEXT_DATA__ script tag.
        """
        races = []

        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            logging.error(f"[{self.source_id}] Could not find __NEXT_DATA__ script tag.")
            return []

        try:
            json_data = json.loads(script_tag.string)
            all_races_data = json_data.get("props", {}).get("pageProps", {}).get("racecards", {}).get("racecards", [])
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"[{self.source_id}] Failed to parse JSON from __NEXT_DATA__: {e}")
            return []

        for race_data in all_races_data:
            try:
                course_name = race_data.get("courseName")
                track_key = canonical_track_key(course_name)
                race_time_str = race_data.get("raceTime")
                race_time = parse_hhmm_any(race_time_str)
                if not race_time:
                    continue

                race_key = canonical_race_key(track_key, race_time)
                race_url = urljoin(self.base_url, race_data.get("raceUrl", ""))

                runners = []
                for runner_data in race_data.get("runners", []):
                    runners.append(RunnerDoc(
                        runner_id=f"{race_key}-{runner_data.get('saddleClothNumber')}",
                        name=FieldConfidence(runner_data.get("horseName"), 0.9, self.source_id),
                        number=FieldConfidence(str(runner_data.get("saddleClothNumber")), 0.9, self.source_id),
                        jockey=FieldConfidence(runner_data.get("jockeyName"), 0.9, self.source_id),
                        trainer=FieldConfidence(runner_data.get("trainerName"), 0.9, self.source_id),
                        odds=FieldConfidence(runner_data.get("odds"), 0.9, self.source_id)
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
                        "race_title": FieldConfidence(race_data.get("raceTitle"), 0.9, self.source_id),
                        "race_url": FieldConfidence(race_url, 0.9, self.source_id)
                    }
                ))
            except Exception as e:
                logging.warning(f"[{self.source_id}] Failed to parse a race entry from JSON: {e}")
                continue

        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races from JSON.")
        return races
