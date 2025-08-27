import csv
import datetime as dt
import logging
from io import StringIO

from ..sources import RawRaceDocument, FieldConfidence, RunnerDoc, register_adapter
from ..fetching import resilient_get
from ..normalizer import canonical_track_key, canonical_race_key
from .base_v3 import BaseAdapterV3


@register_adapter
class BetfairAdapter(BaseAdapterV3):
    """
    V3 Adapter for the Betfair Data Scientists ratings models.

    This adapter fetches CSV data directly from the unofficial API endpoint
    described in the Betfair "How to Automate 3" tutorial.
    """

    source_id = "betfair"

    async def fetch(self) -> list[RawRaceDocument]:
        """
        Fetches and parses the Betfair ratings CSV.
        """
        if not self.is_initialized or not self.site_config:
            logging.error(f"Adapter {self.source_id} is not initialized. Cannot fetch.")
            return []

        # The tutorial describes two models: 'kash-ratings-model' for horses
        # and 'iggy-joey' for greyhounds. We'll use the horse racing one.
        base_url = "https://betfair-data-supplier-prod.herokuapp.com/api/widgets/kash-ratings-model/datasets"
        today_str = dt.date.today().strftime("%Y-%m-%d")
        target_url = f"{base_url}?date={today_str}&presenter=RatingsPresenter&csv=true"

        logging.info(f"[{self.source_id}] Fetching CSV from {target_url}")

        try:
            config = self.config_manager.get_config()
            response = await resilient_get(target_url, config)
            csv_content = response.text
            return self._parse_csv(csv_content)
        except Exception as e:
            logging.error(f"[{self.source_id}] Failed to fetch or parse CSV: {e}", exc_info=True)
            return []

    def _parse_csv(self, csv_content: str) -> list[RawRaceDocument]:
        """Parses the CSV content into RawRaceDocument objects."""
        races = []

        # Use StringIO to treat the CSV string as a file
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)

        # The CSV is flat, so we need to group runners by race.
        # We'll use the 'meetings.races.bfExchangeMarketId' as a race key.
        races_data = {}

        for row in reader:
            try:
                market_id = row.get("meetings.races.bfExchangeMarketId")
                if not market_id:
                    continue

                if market_id not in races_data:
                    # Create a new race document
                    track_name = row.get("meetings.name", "Unknown Track")
                    track_key = canonical_track_key(track_name)
                    race_time = row.get("meetings.races.raceTime", "00:00")
                    race_key = canonical_race_key(track_key, race_time)

                    races_data[market_id] = RawRaceDocument(
                        source_id=self.source_id,
                        fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        track_key=track_key,
                        race_key=race_key,
                        start_time_iso=f"{dt.date.today().isoformat()}T{race_time}:00Z",
                        runners=[],
                        extras={
                            "betfair_market_id": FieldConfidence(market_id, 1.0, self.source_id),
                            "meeting_name": FieldConfidence(track_name, 0.9, self.source_id),
                        },
                    )

                # Add the runner to the race
                runner_doc = RunnerDoc(
                    runner_id=row.get("meetings.races.runners.bfExchangeSelectionId"),
                    name=FieldConfidence(
                        row.get("meetings.races.runners.runnerName"), 0.9, self.source_id
                    ),
                    number=FieldConfidence(
                        row.get("meetings.races.runners.runnerNumber"), 0.9, self.source_id
                    ),
                    odds=FieldConfidence(
                        row.get("meetings.races.runners.ratedPrice"), 0.9, self.source_id
                    ),
                )
                races_data[market_id].runners.append(runner_doc)

            except Exception as e:
                logging.warning(f"[{self.source_id}] Could not parse a row: {row}. Error: {e}")
                continue

        races = list(races_data.values())
        logging.info(f"[{self.source_id}] Successfully parsed {len(races)} races from CSV.")
        return races
