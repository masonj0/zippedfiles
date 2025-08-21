import logging
import datetime as dt
from datetime import date

from .base import BaseV2Adapter
from ..fetching import resilient_get
from ..sources import RawRaceDocument, FieldConfidence, register_adapter
from ..normalizer import canonical_track_key, canonical_race_key, parse_hhmm_any, map_discipline

@register_adapter
class SportingLifeAdapter(BaseV2Adapter):
    """
    Adapter for fetching racecards from the Sporting Life API.
    This adapter now uses the resilient_get function.
    """
    source_id = "sportinglife"

    def _parse_api_data(self, json_data: dict) -> list[RawRaceDocument]:
        """Surgically parses the JSON response from the Sporting Life API."""
        races = []
        meetings = json_data.get('race_meetings', [])
        if not meetings and isinstance(json_data, list):
            meetings = json_data

        for meeting in meetings:
            try:
                course_name = meeting.get('course_name')
                if not course_name:
                    continue
                track_key = canonical_track_key(course_name)

                for race_summary in meeting.get('races', []):
                    start_time_iso = race_summary.get('start_time')
                    if not start_time_iso:
                        continue

                    time_str = parse_hhmm_any(start_time_iso)
                    if not time_str:
                        continue
                    race_key = canonical_race_key(track_key, time_str.replace(":", ""))
                    race_url = f"https://www.sportinglife.com{race_summary.get('race_url', '')}"

                    races.append(RawRaceDocument(
                        source_id=self.source_id,
                        fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        track_key=track_key,
                        race_key=race_key,
                        start_time_iso=start_time_iso,
                        runners=[],
                        extras={
                            "country_code": FieldConfidence(meeting.get('country_code', 'GB/IRE'), 0.9, ".country_code"),
                            "race_class": FieldConfidence(race_summary.get('race_class'), 0.9, ".race_class"),
                            "discipline": FieldConfidence(map_discipline(meeting.get('race_type_code', 'F')), 0.9, ".race_type_code"),
                            "race_url": FieldConfidence(race_url, 0.95, ".race_url")
                        }
                    ))
            except Exception as e:
                logging.error(f"[{self.source_id}] Error parsing a meeting from Sporting Life API: {e}", exc_info=True)
        return races

    async def fetch(self) -> list[RawRaceDocument]:
        # TO-DO: This adapter is non-functional as of 2025-08-19.
        # The API endpoint at /api/horse-racing/race now returns a 400 Bad Request
        # with a maintenance page served from S3/CloudFront.
        # To fix this, a new, valid API endpoint needs to be discovered by
        # inspecting the network traffic on the main sportinglife.com website.
        # The adapter has been disabled in `config_settings.json` for now.
        """Fetches and parses the Sporting Life API using the resilient getter."""
        if not self.site_config:
            return []

        today_str = date.today().isoformat()
        try:
            target_url = self.site_config["url"].format(date_str_iso=today_str)
        except (KeyError, AttributeError):
            logging.error(f"[{self.source_id}] Invalid or unformattable URL in config: {self.site_config.get('url')}")
            return []

        try:
            response = await resilient_get(target_url, config=self.config)
            if not response:
                logging.error(f"[{self.source_id}] Failed to fetch data from API.")
                return []

            json_data = response.json()
            return self._parse_api_data(json_data)
        except Exception as e:
            logging.error(f"[{self.source_id}] An error occurred during fetch or parse: {e}", exc_info=True)
            return []
