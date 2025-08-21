import asyncio
import logging
from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter
from pprint import pprint
from typing import Dict, List, Any, Optional
import importlib
import re

from sources import RawRaceDocument
from normalizer import NormalizedRace, normalize_race_docs
from config_manager import config_manager
from adapters.base_v3 import BaseAdapterV3

# --- Data Structures ---

@dataclass
class ScoreResult:
    """Represents a race after scoring, ready for display."""
    race: NormalizedRace
    score: float
    reason: str
    best_value_score: Optional[float] = None
    best_value_reason: Optional[str] = None

# --- Pipeline Steps ---

def _camel_to_snake(name: str) -> str:
    """Converts a CamelCase string to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def load_adapters_from_config() -> List[BaseAdapterV3]:
    """
    Loads and initializes V3 adapters from the configuration.
    """
    v3_adapters = []
    v3_configs = config_manager.get_config().get("DATA_SOURCES_V3", {})

    for name, config in v3_configs.items():
        if not config.get("enabled", False):
            continue

        try:
            adapter_class_name = config.get("adapter_class")
            # The module name is now expected to be lowercase version of the class name
            # e.g., BetfairDataScientistAdapter -> betfairdatascientistadapter
            module_name = adapter_class_name.lower()

            # Use an absolute module path now that the structure is flat
            module_path = f"adapters.{module_name}"

            adapter_module = importlib.import_module(module_path)
            AdapterClass = getattr(adapter_module, adapter_class_name)

            if issubclass(AdapterClass, BaseAdapterV3):
                adapter_instance = AdapterClass.create_from_config(config['config'])
                v3_adapters.append(adapter_instance)
                logging.info(f"Successfully loaded and created V3 adapter: {name}")
            else:
                logging.warning(f"Class {adapter_class_name} is not a valid V3 adapter.")

        except (ImportError, AttributeError) as e:
            logging.error(f"Failed to load adapter '{name}': {e}", exc_info=True)

    return v3_adapters

async def collect_all() -> List[NormalizedRace]:
    """
    Instantiates and runs all registered source adapters concurrently.
    """
    adapters = load_adapters_from_config()
    logging.info(f"Loaded {len(adapters)} V3 adapters from config.")

    tasks = [adapter.fetch_and_normalize() for adapter in adapters]

    if not tasks:
        logging.warning("No enabled and initialized adapters found to run.")
        return []

    logging.info(f"Running {len(tasks)} adapters concurrently.")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_races = []
    for res in results:
        if isinstance(res, list):
            all_races.extend(res)
        elif isinstance(res, Exception):
            logging.error(f"Adapter failed to fetch: {res}", exc_info=res)

    logging.info(f"Collected {len(all_races)} normalized races from all V3 sources.")
    return all_races


# --- V2 SCORING LOGIC ---

class V2Scorer:
    """
    Analyzes a NormalizedRace to produce a score based on various signals.
    """
    def __init__(self):
        config = config_manager.get_config()
        default_weights = {
            "FIELD_SIZE": 0.25, "FAVORITE_ODDS": 0.35,
            "ODDS_SPREAD": 0.10, "VALUE_VS_SP": 0.30,
        }
        scorer_weights = config.get("SCORER_WEIGHTS", default_weights)
        for key, value in default_weights.items():
            if key not in scorer_weights:
                scorer_weights[key] = value
                logging.warning(f"Missing '{key}' in SCORER_WEIGHTS, using default: {value}")

        total_weight = sum(scorer_weights.values())
        self.weights = {k: v / total_weight for k, v in scorer_weights.items()} if total_weight else default_weights
        logging.info(f"V2Scorer initialized with main weights: {self.weights}")

        default_value_weights = {
            "VALUE_ODDS_WEIGHT": 0.6,
            "VALUE_COMPETITIVENESS_WEIGHT": 0.4
        }
        value_weights = config.get("BEST_VALUE_WEIGHTS", default_value_weights)
        for key, value in default_value_weights.items():
            if key not in value_weights:
                value_weights[key] = value
                logging.warning(f"Missing '{key}' in BEST_VALUE_WEIGHTS, using default: {value}")

        total_value_weight = sum(value_weights.values())
        self.value_weights = {k: v / total_value_weight for k, v in value_weights.items()} if total_value_weight else default_value_weights
        logging.info(f"V2Scorer initialized with value weights: {self.value_weights}")


    def _get_field_size_score(self, field_size: int) -> float:
        if 5 <= field_size <= 7: return 100.0
        if 8 <= field_size <= 10: return 80.0
        if 3 <= field_size <= 4: return 60.0
        if 11 <= field_size <= 12: return 40.0
        return 20.0

    def _get_fav_odds_score(self, fav_odds: Optional[float]) -> float:
        if fav_odds is None: return 20.0
        if fav_odds < 1.5: return 60.0
        if 1.5 <= fav_odds < 2.5: return 100.0
        if 2.5 <= fav_odds < 4.0: return 80.0
        if 4.0 <= fav_odds < 6.0: return 50.0
        return 30.0

    def _get_odds_spread_score(self, fav_odds: Optional[float], sec_fav_odds: Optional[float]) -> float:
        if fav_odds is None or sec_fav_odds is None: return 20.0
        spread = sec_fav_odds - fav_odds
        if spread > 2.0: return 100.0
        if spread > 1.0: return 80.0
        if spread >= 0.5: return 50.0
        return 30.0

    def _get_fav_vs_field_ratio_score(self, runners: list) -> tuple[float, float]:
        if len(runners) < 3: return 20.0, 0.0
        fav_odds = runners[0].odds_decimal
        avg_odds = sum(r.odds_decimal for r in runners) / len(runners)
        if avg_odds == 0: return 0.0, 0.0
        ratio = fav_odds / avg_odds
        if ratio >= 0.8: return 100.0, ratio
        if 0.7 <= ratio < 0.8: return 90.0, ratio
        if 0.5 <= ratio < 0.7: return 70.0, ratio
        if 0.3 <= ratio < 0.5: return 50.0, ratio
        return 40.0, ratio

    def _get_best_value_score(self, runners_with_odds: list) -> tuple[Optional[float], Optional[str]]:
        if len(runners_with_odds) < 3:
            return None, "Not enough runners for value score."

        fav_horse = runners_with_odds[0]
        value_horse = runners_with_odds[2]

        value_horse_odds = value_horse.odds_decimal
        fav_odds = fav_horse.odds_decimal

        if value_horse_odds is None or fav_odds is None:
             return None, "Odds missing for value calculation."

        if 5.0 <= value_horse_odds < 10.0: value_odds_score = 100.0
        elif 10.0 <= value_horse_odds < 15.0: value_odds_score = 80.0
        elif 3.0 <= value_horse_odds < 5.0: value_odds_score = 50.0
        elif value_horse_odds >= 15.0: value_odds_score = 20.0
        else: value_odds_score = 0.0

        spread = value_horse_odds - fav_odds
        if spread < 4.0: competitiveness_score = 100.0
        elif 4.0 <= spread < 8.0: competitiveness_score = 70.0
        else: competitiveness_score = 30.0

        final_value_score = (
            (value_odds_score * self.value_weights["VALUE_ODDS_WEIGHT"]) +
            (competitiveness_score * self.value_weights["VALUE_COMPETITIVENESS_WEIGHT"])
        )

        reason = f"Value Pick: {value_horse.name} ({value_horse_odds:.2f})"
        return round(final_value_score, 2), reason

    def score_race(self, race: NormalizedRace) -> ScoreResult:
        runners_with_odds = sorted(
            [r for r in race.runners if r.odds_decimal is not None],
            key=lambda r: r.odds_decimal
        )

        if len(runners_with_odds) < 2:
            return ScoreResult(race=race, score=0.0, reason="Not enough runners with odds.")

        favorite = runners_with_odds[0]
        second_favorite = runners_with_odds[1]
        fav_odds = favorite.odds_decimal
        sec_fav_odds = second_favorite.odds_decimal
        field_size = len(race.runners)

        field_size_score = self._get_field_size_score(field_size)
        fav_odds_score = self._get_fav_odds_score(fav_odds)
        spread_score = self._get_odds_spread_score(fav_odds, sec_fav_odds)
        fav_ratio_score, fav_ratio = self._get_fav_vs_field_ratio_score(runners_with_odds)

        final_score = (
            (field_size_score * self.weights["FIELD_SIZE"]) +
            (fav_odds_score * self.weights["FAVORITE_ODDS"]) +
            (spread_score * self.weights["ODDS_SPREAD"]) +
            (fav_ratio_score * self.weights["VALUE_VS_SP"])
        )
        reason = (
            f"Field: {field_size} ({field_size_score:.0f}), "
            f"Fav Odds: {fav_odds:.2f} ({fav_odds_score:.0f}), "
            f"Spread: {(sec_fav_odds - fav_odds):.2f} ({spread_score:.0f}), "
            f"FavRatio: {fav_ratio:.2f}({fav_ratio_score:.0f})"
        )

        best_value_score, best_value_reason = self._get_best_value_score(runners_with_odds)

        return ScoreResult(
            race=race,
            score=round(final_score, 2),
            reason=reason,
            best_value_score=best_value_score,
            best_value_reason=best_value_reason
        )

def score_races(races: List[NormalizedRace]) -> List[ScoreResult]:
    config = config_manager.get_config()
    filter_config = config.get("RACE_FILTERS", {})
    min_runners = filter_config.get("MIN_RUNNERS", 0)
    max_runners = filter_config.get("MAX_RUNNERS", 99)

    initial_race_count = len(races)
    filtered_races = [
        race for race in races
        if min_runners <= len(race.runners) <= max_runners
    ]

    if len(filtered_races) < initial_race_count:
        logging.info(
            f"Filtered races by runner count ({min_runners}-{max_runners}). "
            f"Kept {len(filtered_races)} of {initial_race_count} races."
        )

    if not filtered_races:
        return []

    scorer = V2Scorer()
    scored_races = [scorer.score_race(race) for race in filtered_races]

    logging.info(f"Scored {len(scored_races)} races.")
    return sorted(scored_races, key=lambda r: r.score, reverse=True)

# --- Reporting ---

def display_results_console(scored_results: List[ScoreResult]):
    logging.info("--- V2 PIPELINE RESULTS ---")
    if not scored_results:
        print("No races to display.")
        return

    print(f"Displaying top {len(scored_results)} scored races:")
    for result in scored_results:
        print("-" * 50)
        print(f"Race: {result.race.race_key} (Score: {result.score})")
        if result.best_value_score is not None:
            print(f"  Value Score: {result.best_value_score} ({result.best_value_reason})")
        print(f"  Reason: {result.reason}")
        print(f"  Start Time: {result.race.start_time_iso}")
        print(f"  Sources: {', '.join(result.race.source_ids)}")
        print(f"  Runners ({len(result.race.runners)}):")
        sorted_runners = sorted(result.race.runners, key=lambda r: int(r.saddle_cloth) if r.saddle_cloth.isdigit() else 999)
        for runner in sorted_runners:
            odds = f"{runner.odds_decimal:.2f}" if runner.odds_decimal else "N/A"
            print(f"    - {runner.saddle_cloth}. {runner.name} ({odds})")

# --- Main Pipeline Orchestrator ---

async def run_v3_analysis_pipeline() -> List[ScoreResult]:
    logging.info("--- V3 ANALYSIS PIPELINE START ---")

    normalized_races = await collect_all()
    if not normalized_races:
        logging.warning("No normalized races collected from V3 adapters.")
        return []

    scored_results = score_races(normalized_races)

    display_results_console(scored_results)

    logging.info(f"--- V3 ANALYSIS PIPELINE END ---")
    return scored_results
