import asyncio
import datetime as dt
import logging
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from adapters.base import BaseV2Adapter
from fetching import resilient_get
from normalizer import canonical_track_key, canonical_race_key
from sources import (
    FieldConfidence,
    RawRaceDocument,
    RunnerDoc,
    register_adapter,
)

@register_adapter
class TimeformAdapter(BaseV2Adapter):
    """
    Adapter for fetching racecards from Timeform.
    This adapter performs a two-stage fetch and now uses the resilient_get
    function for improved reliability.
    """
    source_id = "timeform"

    def _parse_runner_data(self, race_soup: BeautifulSoup) -> list[RunnerDoc]:
        """Parses the runner data from a single Timeform race page."""
        runners = []
        runner_rows = race_soup.select("tbody.rp-horse-row")
        for row in runner_rows:
            try:
                name_el = row.select_one("a.rp-horse")
                saddle_cloth_el = row.select_one("span.rp-entry-number")
                jockey_el = row.select_one('a[title="Jockey"]')
                trainer_el = row.select_one('a[title="Trainer"]')
                odds_el = row.select_one("span.price-decimal")

                if not all([name_el, saddle_cloth_el, jockey_el, trainer_el]): continue

                horse_name = name_el.get_text(strip=True)
                saddle_cloth = saddle_cloth_el.get_text(strip=True)
                runner_id = f"{saddle_cloth}-{horse_name}".lower().replace(" ", "-")
                odds = FieldConfidence(odds_el.get_text(strip=True), 0.95, "span.price-decimal") if odds_el else None

                runners.append(RunnerDoc(
                    runner_id=runner_id,
                    name=FieldConfidence(horse_name, 0.95, "a.rp-horse"),
                    number=FieldConfidence(saddle_cloth, 0.95, "span.rp-entry-number"),
                    odds=odds,
                    jockey=FieldConfidence(jockey_el.get_text(strip=True), 0.9, 'a[title="Jockey"]'),
                    trainer=FieldConfidence(trainer_el.get_text(strip=True), 0.9, 'a[title="Trainer"]')
                ))
            except Exception as e:
                logging.error(f"Failed to parse a runner row on Timeform: {e}", exc_info=True)
        return runners

    def _parse_race_list(self, html_content: str) -> list[str]:
        """Parses the main race list page to extract URLs for individual races."""
        soup = BeautifulSoup(html_content, "html.parser")
        base_url = self.site_config.get("base_url", "https://www.timeform.com")
        race_links = {
            urljoin(base_url, a['href'])
            for a in soup.find_all("a", href=True)
            if a['href'] and a['href'].startswith('/horse-racing/racecards/') and len(a['href'].strip('/').split('/')) >= 5
        }
        return list(race_links)

    async def fetch_race_details(self, doc: RawRaceDocument):
        """A helper to fetch details for a single race asynchronously."""
        try:
            race_url = doc.extras.get("race_url").value
            if not race_url: return

            detail_response = await resilient_get(race_url)
            if not detail_response:
                logging.warning(f"[{self.source_id}] Failed to fetch detail for race {doc.race_key}, skipping.")
                return

            detail_soup = BeautifulSoup(detail_response.text, 'lxml')
            doc.runners = self._parse_runner_data(detail_soup)
            logging.info(f"-> Found {len(doc.runners)} runners for race {doc.race_key}")
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse detail for race {doc.race_key}: {e}", exc_info=True)

    async def fetch(self) -> list[RawRaceDocument]:
        """Fetches Timeform racecards and details using the resilient getter."""
        if not self.site_config: return []

        target_url = self.site_config.get("url")
        if not target_url:
            logging.error("Timeform url not configured.")
            return []

        logging.info(f"[{self.source_id}] Fetching Timeform race list...")
        try:
            list_response = await resilient_get(target_url)
            if not list_response: raise Exception("Failed to fetch race list")
            list_html = list_response.text
        except Exception as e:
            logging.error(f"[{self.source_id}] An error occurred while fetching Timeform race list: {e}")
            return []

        race_urls = self._parse_race_list(list_html)
        logging.info(f"[{self.source_id}] Found {len(race_urls)} race URLs to process.")

        race_docs = []
        for url in race_urls:
            try:
                path_parts = urlparse(url).path.strip('/').split('/')
                track_key = canonical_track_key(path_parts[2].replace('-', ' '))
                time_str = path_parts[4]
                race_docs.append(RawRaceDocument(
                    source_id=self.source_id,
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    track_key=track_key,
                    race_key=canonical_race_key(track_key, time_str),
                    start_time_iso=f"{path_parts[3]}T{time_str[:2]}:{time_str[2:]}:00Z",
                    runners=[],
                    extras={"race_url": FieldConfidence(url, 0.9, "a[href] parsed from page")}
                ))
            except Exception as e:
                logging.error(f"[{self.source_id}] Failed to parse race info from URL {url}: {e}")

        await asyncio.gather(*(self.fetch_race_details(doc) for doc in race_docs))

        successful_docs = [doc for doc in race_docs if doc.runners]
        logging.info(f"[{self.source_id}] Successfully fetched runner data for {len(successful_docs)} of {len(race_docs)} races.")
        return successful_docs
