import pandas as pd
import requests
from datetime import datetime
from io import StringIO
import re

from normalizer import NormalizedRace, NormalizedRunner
from adapters.base_v3 import BaseAdapterV3


class BetfairDataScientistAdapter(BaseAdapterV3):
    """
    Adapter for fetching and parsing data from the Betfair Data Scientists API.
    """

    ADAPTER_NAME = "BetfairDataScientist"

    def __init__(self, model_name: str, url: str, enabled: bool = True, priority: int = 100):
        super().__init__(f"{self.ADAPTER_NAME}_{model_name}", enabled, priority)
        self.model_name = model_name
        self.url = url
        self.logger.info(f"Initialized BetfairDataScientistAdapter for model: {self.model_name}")

    def fetch_and_normalize(self) -> list[NormalizedRace]:
        if not self.is_enabled():
            self.logger.debug(f"Adapter '{self.get_name()}' is disabled. Skipping.")
            return []

        try:
            full_url = self._build_url()
            self.logger.info(f"Fetching data from {full_url}")

            response = requests.get(full_url)
            response.raise_for_status()

            csv_data = response.text
            if not csv_data.strip():
                self.logger.warning(f"No data returned from API for {self.model_name}.")
                return []

            df = pd.read_csv(StringIO(csv_data))
            return self._normalize_df(df)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching data for {self.model_name}: {e}")
            return []
        except pd.errors.EmptyDataError:
            self.logger.warning(f"Empty CSV returned from API for {self.model_name}.")
            return []
        except Exception as e:
            self.logger.error(f"An unexpected error in {self.get_name()}: {e}", exc_info=True)
            return []

    def _normalize_df(self, df: pd.DataFrame) -> list[NormalizedRace]:
        """Transforms the DataFrame into a list of NormalizedRace objects."""

        df = df.rename(
            columns={
                "meetings.races.bfExchangeMarketId": "market_id",
                "meetings.races.runners.bfExchangeSelectionId": "selection_id",
                "meetings.races.runners.ratedPrice": "rated_price",
                "meetings.races.raceName": "race_name",
                "meetings.name": "meeting_name",
                "meetings.races.raceNumber": "race_number",
                "meetings.races.runners.runnerName": "runner_name",
                "meetings.races.runners.clothNumber": "saddle_cloth",
            }
        )

        required = ["market_id", "selection_id", "rated_price", "runner_name"]
        if not all(col in df.columns for col in required):
            self.logger.error("CSV from API is missing required columns.")
            return []

        normalized_races = []
        for market_id, group in df.groupby("market_id"):
            race_info = group.iloc[0]

            runners = []
            for _, row in group.iterrows():
                runner = NormalizedRunner(
                    runner_id=str(row.get("selection_id")),
                    name=str(row.get("runner_name")),
                    saddle_cloth=str(row.get("saddle_cloth", "")),
                    odds_decimal=float(row.get("rated_price", 0.0)),
                )
                runners.append(runner)

            race = NormalizedRace(
                race_key=str(market_id),
                track_key=normalize_course_name(str(race_info.get("meeting_name", ""))),
                start_time_iso=datetime.now().isoformat(),
                race_name=str(race_info.get("race_name", "")),
                runners=runners,
                source_ids=[self.get_name()],
            )
            normalized_races.append(race)

        self.logger.info(f"Normalized {len(normalized_races)} races from {self.model_name}.")
        return normalized_races

    def _build_url(self) -> str:
        todays_date = datetime.now().strftime("%Y-%m-%d")
        return f"{self.url}{todays_date}&presenter=RatingsPresenter&csv=true"

    @classmethod
    def create_from_config(cls, config: dict) -> "BetfairDataScientistAdapter":
        return cls(
            model_name=config.get("model_name"),
            url=config.get("url"),
            enabled=config.get("enabled", True),
            priority=config.get("priority", 100),
        )


def normalize_course_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name
