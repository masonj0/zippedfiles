import asyncio
import logging
from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter
from pprint import pprint
from typing import Dict, List, Any, Optional

from sources import ADAPTERS, RawRaceDocument
from normalizer import NormalizedRace, normalize_race_docs
from config import load_config
import adapters

# --- Data Structures ---

@dataclass
class ScoreResult:
    """Represents a race after scoring, ready for display."""
    race: NormalizedRace
    score: float
    reason: str

# --- Pipeline Steps ---

async def collect_all(config: Dict[str, Any]) -> List[RawRaceDocument]:
    """
    Instantiates and runs all registered source adapters concurrently.
    """
    logging.info(f"Found {len(ADAPTERS)} registered adapters.")

    adapters = [adapter(config) for adapter in ADAPTERS]

    # Filter out adapters that were disabled during initialization
    enabled_adapters = [adapter for adapter in adapters if hasattr(adapter, 'site_config') and adapter.site_config is not None]

    if not enabled_adapters:
        logging.warning("No enabled adapters found in the configuration.")
        return []

    logging.info(f"Running {len(enabled_adapters)} enabled adapters.")
    tasks = [adapter.fetch() for adapter in enabled_adapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_docs = []
    for res in results:
        if isinstance(res, list):
            all_docs.extend(res)
        elif isinstance(res, Exception):
            logging.error(f"Adapter failed to fetch: {res}", exc_info=res)

    logging.info(f"Collected {len(all_docs)} raw race documents from all sources.")
    return all_docs

def coalesce_docs(docs: List[RawRaceDocument]) -> Dict[str, List[RawRaceDocument]]:
    """
    Groups raw race documents by their unique race_key.
    """
    if not docs:
        return {}

    sorted_docs = sorted(docs, key=attrgetter("race_key"))

    grouped_by_race = {
        key: list(group)
        for key, group in groupby(sorted_docs, key=attrgetter("race_key"))
    }

    logging.info(f"Coalesced {len(docs)} documents into {len(grouped_by_race)} unique races.")
    return grouped_by_race

def normalize_and_merge(race_docs: List[RawRaceDocument]) -> NormalizedRace:
    """
    Normalizes a list of documents for the same race and merges them.
    """
    if not race_docs:
        raise ValueError("Cannot normalize an empty list of documents.")

    base_normalized_race = normalize_race_docs(race_docs[0])

    for doc in race_docs[1:]:
        if doc.source_id not in base_normalized_race.source_ids:
            base_normalized_race.source_ids.append(doc.source_id)

    return base_normalized_race

# --- V2 SCORING LOGIC ---

class V2Scorer:
    """
    Analyzes a NormalizedRace to produce a score based on various signals.
    Weights are now loaded from the configuration file for easy tuning.
    """
    def __init__(self, config: Dict):
        # Define default weights as a fallback
        default_weights = {
            "FIELD_SIZE": 0.25,
            "FAVORITE_ODDS": 0.35,
            "ODDS_SPREAD": 0.10,
            "VALUE_VS_SP": 0.30,
        }

        # Load weights from config, falling back to defaults
        scorer_weights = config.get("SCORER_WEIGHTS", default_weights)

        # Ensure all required keys are present
        for key, value in default_weights.items():
            if key not in scorer_weights:
                scorer_weights[key] = value
                logging.warning(f"Missing '{key}' in SCORER_WEIGHTS, using default value: {value}")

        # Normalize weights to ensure they sum to 1.0
        total_weight = sum(scorer_weights.values())
        if total_weight == 0:
            logging.error("Total scorer weight is zero. Using default weights instead.")
            self.weights = default_weights
        else:
            self.weights = {key: value / total_weight for key, value in scorer_weights.items()}

        logging.info(f"V2Scorer initialized with weights: {self.weights}")

    def _get_field_size_score(self, field_size: int) -> float:
        if 5 <= field_size <= 7:
            return 100.0
        if 8 <= field_size <= 10:
            return 80.0
        if 3 <= field_size <= 4:
            return 60.0
        if 11 <= field_size <= 12:
            return 40.0
        return 20.0

    def _get_fav_odds_score(self, fav_odds: Optional[float]) -> float:
        if fav_odds is None:
            return 20.0  # Assign a low score if odds are missing
        if fav_odds < 1.5:  # Odds-on
            return 60.0
        if 1.5 <= fav_odds < 2.5:
            return 100.0
        if 2.5 <= fav_odds < 4.0:
            return 80.0
        if 4.0 <= fav_odds < 6.0:
            return 50.0
        return 30.0

    def _get_odds_spread_score(self, fav_odds: Optional[float], sec_fav_odds: Optional[float]) -> float:
        if fav_odds is None or sec_fav_odds is None:
            return 20.0

        spread = sec_fav_odds - fav_odds
        if spread > 2.0:
            return 100.0
        if spread > 1.0:
            return 80.0
        if spread >= 0.5:
            return 50.0
        return 30.0

    def _get_fav_vs_field_ratio_score(self, runners: list) -> tuple[float, float]:
        """
        Calculates a score based on the ratio of the favorite's odds to the
        average odds of the field. A higher ratio suggests a more competitive race.
        """
        runners_with_odds = [r for r in runners if r.odds_decimal is not None]

        if len(runners_with_odds) < 3:
            return 20.0, 0.0

        runners_with_odds.sort(key=lambda r: r.odds_decimal)

        fav_odds = runners_with_odds[0].odds_decimal
        avg_odds = sum(r.odds_decimal for r in runners_with_odds) / len(runners_with_odds)

        if avg_odds == 0:
            return 0.0, 0.0

        # A ratio closer to 1.0 means the favorite is not much lower than the average,
        # indicating a more open, competitive race.
        ratio = fav_odds / avg_odds

        if ratio >= 0.8: return 100.0, ratio
        if 0.7 <= ratio < 0.8: return 90.0, ratio
        if 0.5 <= ratio < 0.7: return 70.0, ratio
        if 0.3 <= ratio < 0.5: return 50.0, ratio
        return 40.0, ratio

    def score_race(self, race: NormalizedRace) -> ScoreResult:
        """Calculates a score for a single normalized race."""

        runners_with_odds = sorted(
            [r for r in race.runners if r.odds_decimal is not None],
            key=lambda r: r.odds_decimal
        )

        if len(runners_with_odds) < 2:
            return ScoreResult(race=race, score=0.0, reason="Not enough runners with odds to score.")

        favorite = runners_with_odds[0]
        second_favorite = runners_with_odds[1]

        fav_odds = favorite.odds_decimal
        sec_fav_odds = second_favorite.odds_decimal
        field_size = len(race.runners)

        # Calculate component scores
        field_size_score = self._get_field_size_score(field_size)
        fav_odds_score = self._get_fav_odds_score(fav_odds)
        spread_score = self._get_odds_spread_score(fav_odds, sec_fav_odds)
        fav_ratio_score, fav_ratio = self._get_fav_vs_field_ratio_score(runners_with_odds)

        # Calculate final weighted score
        # Note: The weight key "VALUE_VS_SP" is kept for config compatibility
        final_score = (
            (field_size_score * self.weights["FIELD_SIZE"]) +
            (fav_odds_score * self.weights["FAVORITE_ODDS"]) +
            (spread_score * self.weights["ODDS_SPREAD"]) +
            (fav_ratio_score * self.weights["VALUE_VS_SP"])
        )

        reason = (
            f"Field Size: {field_size} ({field_size_score:.0f}), "
            f"Fav Odds: {fav_odds:.2f} ({fav_odds_score:.0f}), "
            f"Spread: {(sec_fav_odds - fav_odds):.2f} ({spread_score:.0f}), "
            f"FavRatio: {fav_ratio:.2f}({fav_ratio_score:.0f})"
        )

        return ScoreResult(race=race, score=round(final_score, 2), reason=reason)

def score_races(races: List[NormalizedRace], config: Dict) -> List[ScoreResult]:
    """
    Scores a list of normalized races using the V2Scorer.
    """
    scorer = V2Scorer(config)
    scored_races = [scorer.score_race(race) for race in races]

    logging.info(f"Scored {len(scored_races)} races.")
    return sorted(scored_races, key=lambda r: r.score, reverse=True)

# --- Reporting ---

def display_results_console(scored_results: List[ScoreResult]):
    """
    Displays the final scored results in a user-friendly format on the console.
    """
    logging.info("--- V2 PIPELINE RESULTS ---")
    if not scored_results:
        print("No races to display.")
        return

    print(f"Displaying top {len(scored_results)} scored races:")
    for result in scored_results:
        print("-" * 50)
        print(f"Race: {result.race.race_key} (Score: {result.score})")
        print(f"  Reason: {result.reason}")
        print(f"  Start Time: {result.race.start_time_iso}")
        print(f"  Sources: {', '.join(result.race.source_ids)}")
        print(f"  Runners ({len(result.race.runners)}):")
        # Sort runners by saddle cloth number for consistent display
        sorted_runners = sorted(result.race.runners, key=lambda r: int(r.saddle_cloth) if r.saddle_cloth.isdigit() else 999)
        for runner in sorted_runners:
            odds = f"{runner.odds_decimal:.2f}" if runner.odds_decimal else "N/A"
            print(f"    - {runner.saddle_cloth}. {runner.name} ({odds})")

# --- Main Pipeline Orchestrator ---

def normalize_races_from_docs(raw_docs: List[RawRaceDocument]) -> List[NormalizedRace]:
    """
    Takes a list of RawRaceDocuments and processes them into a list of
    unique, merged, and normalized NormalizedRace objects.
    """
    if not raw_docs:
        return []

    races_by_key = coalesce_docs(raw_docs)

    normalized_races = []
    for race_key, docs in races_by_key.items():
        try:
            normalized_race = normalize_and_merge(docs)
            normalized_races.append(normalized_race)
        except Exception as e:
            logging.error(f"Failed to normalize race {race_key}: {e}", exc_info=True)

    return normalized_races

async def run_v2_adapter_pipeline(config: Dict[str, Any]) -> List[NormalizedRace]:
    """
    The main entry point for the V2 data processing pipeline. It now returns
    a list of normalized races instead of printing them.
    """
    logging.info("--- V2 ADAPTER PIPELINE START ---")

    raw_docs = await collect_all(config)
    if not raw_docs:
        logging.warning("No raw documents collected from V2 adapters.")
        return []

    normalized_races = normalize_races_from_docs(raw_docs)
    if not normalized_races:
        logging.warning("No races were successfully normalized from V2 adapters.")
        return []

    logging.info(f"--- V2 ADAPTER PIPELINE END: Produced {len(normalized_races)} normalized races. ---")
    return normalized_races
