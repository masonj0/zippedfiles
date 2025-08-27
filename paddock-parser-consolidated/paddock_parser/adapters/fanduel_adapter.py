import copy
import httpx
from datetime import datetime
from paddock_parser.normalizer import NormalizedRace, NormalizedRunner
from .base_v3 import BaseAdapterV3, RawRaceDocument, register_adapter


@register_adapter
class FanDuelAdapter(BaseAdapterV3):
    source_id = "fanduel"

    _GRAPHQL_ENDPOINT = "https://api.racing.fanduel.com/cosmo/v1/graphql"
    _HEADERS = {
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    _SCHEDULE_PAYLOAD = {
        "operationName": "getLhnInfo",
        "variables": {
            "withGreyhounds": False,
            "brand": "FDR",
            "product": "TVG5",
            "device": "Desktop",
            "noLoggedIn": True,
            "wagerProfile": "FDR-Generic",
        },
        "query": 'query getLhnInfo($wagerProfile: String, $withGreyhounds: Boolean, $noLoggedIn: Boolean!, $product: String, $device: String, $brand: String) {\n  scheduleRaces: tracks(profile: $wagerProfile) {\n    id\n    races(\n      filter: {status: ["MO", "O", "SK", "IC"], allRaceClasses: $withGreyhounds}\n      page: {results: 2, current: 0}\n      sort: {byMTP: ASC}\n    ) {\n      id\n      tvgRaceId\n      mtp\n      number\n      postTime\n      isGreyhound\n      location {\n        country\n        __typename\n      }\n      track {\n        id\n        isFavorite @skip(if: $noLoggedIn)\n        code\n        name\n        perfAbbr\n        featured\n        hasWagersToday @skip(if: $noLoggedIn)\n        __typename\n      }\n      type {\n        code\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n',
    }

    _DETAILS_PAYLOAD = {
        "operationName": "getGraphRaceBettingInterest",
        "variables": {"tvgRaceIds": [], "tvgRaceIdsBiPartial": [], "wagerProfile": "FDR-Generic"},
        "query": "query getGraphRaceBettingInterest($tvgRaceIds: [Long], $tvgRaceIdsBiPartial: [Long], $wagerProfile: String) {\n  races: races(\n    tvgRaceIds: $tvgRaceIds\n    profile: $wagerProfile\n    sorts: [{byRaceNumber: ASC}]\n  ) {\n    id\n    tvgRaceId\n    bettingInterests {\n      biNumber\n      currentOdds {\n        numerator\n        denominator\n        __typename\n      }\n      runners {\n        runnerId\n        scratched\n        horseName\n        jockey\n        trainer\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
    }

    async def _fetch_schedule(self, client: httpx.AsyncClient) -> list[dict]:
        """Phase 1: Fetches the race schedule and creates an interim list."""
        response = await client.post(
            self._GRAPHQL_ENDPOINT, headers=self._HEADERS, json=self._SCHEDULE_PAYLOAD, timeout=10.0
        )
        response.raise_for_status()
        schedule_data = response.json()

        interim_races = []
        tracks = schedule_data.get("data", {}).get("scheduleRaces", [])
        for track in tracks:
            for race in track.get("races", []):
                race_type = race.get("type", {}).get("code")
                if race_type in ["H", "T"]:
                    interim_races.append(
                        {
                            "tvgRaceId": race.get("tvgRaceId"),
                            "race_id": race.get("id"),
                            "track_name": track.get("name"),
                            "race_number": race.get("number"),
                            "post_time": datetime.fromisoformat(race.get("postTime")),
                            "race_type": race_type,
                        }
                    )
        return interim_races

    async def _fetch_race_details(self, client: httpx.AsyncClient, tvg_race_id: int) -> dict:
        """Fetches the detailed information for a single race."""
        payload = copy.deepcopy(self._DETAILS_PAYLOAD)
        payload["variables"]["tvgRaceIds"] = [tvg_race_id]

        response = await client.post(
            self._GRAPHQL_ENDPOINT, headers=self._HEADERS, json=payload, timeout=10.0
        )
        response.raise_for_status()
        return response.json()

    def _calculate_odds(self, odds_data: dict) -> float | None:
        """Calculates odds from numerator and denominator."""
        if not odds_data:
            return None
        numerator = odds_data.get("numerator")
        denominator = odds_data.get("denominator")
        if numerator is None:
            return None
        if denominator is not None and denominator != 0:
            return numerator / denominator
        return float(numerator)

    async def fetch(self) -> list[RawRaceDocument]:
        """Orchestrates the two-stage fetch process."""
        normalized_races = []
        async with httpx.AsyncClient() as client:
            # Phase 1: Get the schedule
            interim_races = await self._fetch_schedule(client)

            # Phase 2: Get details for each race
            for interim_race in interim_races:
                details_data = await self._fetch_race_details(client, interim_race["tvgRaceId"])

                race_details_list = details_data.get("data", {}).get("races", [])
                if not race_details_list:
                    continue

                race_details = race_details_list[0]
                runners = []
                for interest in race_details.get("bettingInterests", []):
                    runner_info = interest.get("runners", [{}])[0]
                    if not runner_info:
                        continue

                    normalized_runner = NormalizedRunner(
                        name=runner_info.get("horseName"),
                        runner_number=interest.get("biNumber"),
                        jockey=runner_info.get("jockey"),
                        trainer=runner_info.get("trainer"),
                        is_scratched=runner_info.get("scratched", False),
                        odds=self._calculate_odds(interest.get("currentOdds")),
                    )
                    runners.append(normalized_runner)

                normalized_race = NormalizedRace(
                    race_id=interim_race["race_id"],
                    track_id=None,  # Not available in this flow
                    track_name=interim_race["track_name"],
                    race_number=interim_race["race_number"],
                    post_time=interim_race["post_time"],
                    race_type=interim_race["race_type"],
                    runners=runners,
                )

                raw_doc = RawRaceDocument(
                    source_id=self.source_id,
                    race_id=normalized_race.race_id,
                    document=normalized_race,
                )
                normalized_races.append(raw_doc)

        return normalized_races
