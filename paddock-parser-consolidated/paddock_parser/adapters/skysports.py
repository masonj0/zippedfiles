import datetime as dt
import logging
import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from ..sources import RawRaceDocument, FieldConfidence, RunnerDoc, register_adapter
from ..fetching import resilient_get
from ..normalizer import canonical_track_key, canonical_race_key, map_discipline
from .base_v3 import BaseAdapterV3


@register_adapter
class SkySportsAdapter(BaseAdapterV3):
    """
    V3 Adapter for skysports.com.

    NOTE: This is a scaffolded implementation. The parsing logic requires
    CSS selectors that must be identified by a human using browser
    developer tools, as the target page is complex and loads content
    dynamically.
    """

    source_id = "skysports"

    async def fetch(self) -> list[RawRaceDocument]:
        """
        Fetches race data from Sky Sports.
        """
        if not self.is_initialized or not self.site_config:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        target_url = self.site_config.get("url")
        if not target_url:
            logging.error(f"[{self.source_id}] URL not configured.")
            return []

        # NOTE: Playwright bootstrapping has been removed as it is not supported
        # in the current execution environment. This adapter may fail on sites
        # with advanced anti-bot measures.

        logging.info(f"[{self.source_id}] Fetching main racecards page...")
        try:
            config = self.config_manager.get_config()
            response = await resilient_get(target_url, config)
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_races(soup)
        except Exception as e:
            logging.error(
                f"[{self.source_id}] Failed to fetch or parse race list: {e}", exc_info=True
            )
            return []

    def _parse_races(self, soup: BeautifulSoup) -> list[RawRaceDocument]:
        """Parses the racecards page to extract race data using logic from Gemini."""
        races = []

        # Gemini's code uses '.sdc-site-racing-meetings__event' to find each race meeting.
        # This is a much better starting point.
        meeting_containers = soup.select("div.sdc-site-racing-meetings__event")
        logging.info(
            f"[{self.source_id}] Found {len(meeting_containers)} potential race containers."
        )

        for container in meeting_containers:
            try:
                racecard_tag = container.find("a", class_="sdc-site-racing-meetings__event-link")
                if not racecard_tag or not racecard_tag.get("href"):
                    continue

                racecard_url = urljoin("https://www.skysports.com", racecard_tag.get("href"))

                # Extract info from the URL as a fallback
                path_parts = urlparse(racecard_url).path.strip("/").split("/")
                course_name_from_url = "Unknown"
                if "racecards" in path_parts:
                    idx = path_parts.index("racecards")
                    if len(path_parts) > idx + 1:
                        course_name_from_url = path_parts[idx + 1].replace("-", " ").title()

                details_parts = [
                    span.get_text(strip=True)
                    for span in container.find_all(
                        "span",
                        class_=[
                            "sdc-site-racing-meetings__event-name",
                            "sdc-site-racing-meetings__event-details",
                        ],
                    )
                ]
                details_text = " ".join(details_parts)

                time_match = re.search(r"\b(\d{1,2}:\d{2})\b", details_text)
                runners_match = re.search(r"(\d+)\s+runners?", details_text, re.IGNORECASE)

                if not time_match or not runners_match:
                    continue

                race_time = time_match.group(1)
                num_runners = int(runners_match.group(1))
                track_key = canonical_track_key(course_name_from_url)
                race_key = canonical_race_key(track_key, race_time)

                placeholder_runners = [
                    RunnerDoc(
                        runner_id=f"{race_key}-{i + 1}",
                        name=FieldConfidence(f"Runner {i + 1}", 0.1, self.source_id),
                        number=FieldConfidence(str(i + 1), 0.1, self.source_id),
                    )
                    for i in range(num_runners)
                ]

                race_doc = RawRaceDocument(
                    source_id=self.source_id,
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    track_key=track_key,
                    race_key=race_key,
                    start_time_iso=f"{dt.date.today().isoformat()}T{race_time}:00Z",
                    runners=placeholder_runners,
                    extras={
                        "race_title": FieldConfidence(details_text, 0.9, self.source_id),
                        "race_url": FieldConfidence(racecard_url, 0.9, self.source_id),
                        "discipline": FieldConfidence(
                            map_discipline(details_text), 0.5, self.source_id
                        ),
                    },
                )
                races.append(race_doc)

            except Exception as e:
                logging.warning(f"[{self.source_id}] Could not parse a race container: {e}")
                continue

        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races.")
        return races
