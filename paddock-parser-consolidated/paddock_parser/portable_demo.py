# =============================================================================
# --- HEADER ---
# =============================================================================
"""
Paddock Parser Toolkit v2.2 - Portable Showcase

Purpose:
This script is a self-contained, functional showcase of the Paddock Parser
Toolkit's core capabilities. It is designed for end-users to easily run the
analysis and see the generated output, including a detailed HTML report.

It consolidates all necessary logic into one file and runs a simplified
version of the main analysis pipeline, fetching data from a limited set of
live sources and generating a report in the `output` directory.

Requirements:
- A `config_settings.json` file must be present in the same directory.
- A `template_paddock.html` file must be present for report generation.
- Dependencies: pip install nest_asyncio httpx beautifulsoup4 curl_cffi jinja2 tqdm pytz certifi
"""

# =============================================================================
# --- IMPORTS ---
# =============================================================================
import argparse
import asyncio
import json
import logging
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Type
from urllib.parse import urlparse

import nest_asyncio

# Third-party imports - sorted alphabetically
try:
    import certifi
    import httpx
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as e:
    print(f"FATAL: Missing required dependency: {e.name}", file=sys.stderr)
    print(
        "Please install requirements: pip install nest_asyncio httpx beautifulsoup4 curl_cffi jinja2 tqdm pytz certifi",
        file=sys.stderr,
    )
    sys.exit(1)

nest_asyncio.apply()


# =============================================================================
# --- CONFIGURATION LOADER ---
# =============================================================================
def load_config(path: str = "config_settings.json") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file '{path}' not found. Using empty config.")
        return {}
    except json.JSONDecodeError as e:
        logging.critical(f"FATAL: Could not parse config file '{path}': {e}.")
        sys.exit(1)


_config = load_config()
FINGERPRINTS = _config.get("FINGERPRINTS", [{"User-Agent": "Mozilla/5.0"}])
STEALTH_HEADERS = _config.get("STEALTH_HEADERS", {})
CACHE_BUST_HEADERS = _config.get("CACHE_BUST_HEADERS", {})
BIZ_HOURS = _config.get("BIZ_HOURS", {})

# =============================================================================
# --- DATA STRUCTURES ---
# =============================================================================
ADAPTERS: List[Type["SourceAdapter"]] = []


@dataclass
class FieldConfidence:
    value: Any
    confidence: float
    source: str


@dataclass
class RunnerDoc:
    runner_id: str
    name: FieldConfidence
    number: FieldConfidence
    odds: Optional[FieldConfidence] = None
    jockey: Optional[FieldConfidence] = None
    trainer: Optional[FieldConfidence] = None
    extras: Dict[str, FieldConfidence] = field(default_factory=dict)


@dataclass
class RawRaceDocument:
    source_id: str
    fetched_at: str
    track_key: str
    race_key: str
    start_time_iso: str
    runners: List[RunnerDoc]
    extras: Dict[str, FieldConfidence] = field(default_factory=dict)


@dataclass
class NormalizedRunner:
    runner_id: str
    name: str
    saddle_cloth: str
    odds_decimal: Optional[float] = None
    odds_fractional: Optional[str] = None
    jockey_name: Optional[str] = None
    trainer_name: Optional[str] = None
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedRace:
    race_key: str
    track_key: str
    start_time_iso: str
    race_name: Optional[str] = None
    going: Optional[str] = None
    runners: List[NormalizedRunner] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreResult:
    """Represents a race after scoring, ready for display."""

    race: NormalizedRace
    score: float
    reason: str
    best_value_score: Optional[float] = None
    best_value_reason: Optional[str] = None


class SourceAdapter(Protocol):
    source_id: str

    def __init__(self, config: Dict[str, Any]): ...
    async def fetch(self) -> List[RawRaceDocument]: ...


def register_adapter(cls: Type[SourceAdapter]) -> Type[SourceAdapter]:
    if not hasattr(cls, "source_id"):
        raise TypeError(f"Adapter {cls.__name__} must have a 'source_id' attribute.")
    if cls not in ADAPTERS:
        logging.info(f"Registering adapter: {cls.__name__} for source '{cls.source_id}'")
        ADAPTERS.append(cls)
    return cls


# =============================================================================
# --- NORMALIZER FUNCTIONS ---
# =============================================================================
def canonical_track_key(name: str) -> str:
    if not name:
        return "unknown_track"
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    return re.sub(r"[\s-]+", "_", name)


def canonical_race_key(track_key: str, race_time: str) -> str:
    return f"{track_key}::r{re.sub(r'[^0-9]', '', race_time)}"


def normalize_course_name(name: str) -> str:
    # Simplified for demo
    return name.lower().strip()


def map_discipline(discipline_name: str) -> str:
    d_lower = discipline_name.lower()
    if "greyhound" in d_lower:
        return "greyhound"
    if "harness" in d_lower:
        return "harness"
    return "thoroughbred"


def parse_hhmm_any(time_text: str) -> Optional[str]:
    if not time_text:
        return None
    match = re.search(r"(\d{1,2})[:.](\d{2})", str(time_text))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if "pm" in str(time_text).lower() and hour != 12:
        hour += 12
    if "am" in str(time_text).lower() and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def convert_odds_to_decimal(odds_str: str) -> Optional[float]:
    if not isinstance(odds_str, str) or not odds_str.strip():
        return None
    s = odds_str.strip().upper().replace("-", "/")
    if s in {"SP", "NR", "SCR", "VOID"}:
        return None
    if s in {"EVS", "EVENS"}:
        return 2.0
    if "/" in s:
        try:
            num, den = map(float, s.split("/", 1))
            return (num / den) + 1.0 if den > 0 else None
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(s) if float(s) > 1.0 else None
    except ValueError:
        return None


def normalize_race_docs(doc: RawRaceDocument) -> NormalizedRace:
    runners = [
        NormalizedRunner(
            runner_id=r.runner_id,
            name=r.name.value,
            saddle_cloth=r.number.value,
            odds_decimal=convert_odds_to_decimal(r.odds.value if r.odds else None),
            odds_fractional=r.odds.value if r.odds else None,
        )
        for r in doc.runners
    ]
    return NormalizedRace(
        race_key=doc.race_key,
        track_key=doc.track_key,
        start_time_iso=doc.start_time_iso,
        runners=runners,
        source_ids=[doc.source_id],
        extras={k: v.value for k, v in doc.extras.items()},
    )


# =============================================================================
# --- ADVANCED FETCHER ---
# =============================================================================
class FetchingError(Exception):
    pass


class BlockingDetectedError(FetchingError):
    pass


_shared_async_client: Optional[httpx.AsyncClient] = None
_request_history: Dict[str, float] = {}


def get_shared_async_client(fresh_session: bool = False) -> httpx.AsyncClient:
    global _shared_async_client
    if _shared_async_client is None or _shared_async_client.is_closed or fresh_session:
        if _shared_async_client and not _shared_async_client.is_closed:
            asyncio.create_task(_shared_async_client.aclose())
        headers = random.choice(FINGERPRINTS).copy()
        _shared_async_client = httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, headers=headers, verify=certifi.where()
        )
        logging.info("Initialized new shared httpx client")
    return _shared_async_client


async def resilient_get(url: str, config: dict, attempts: int = 3) -> httpx.Response:
    scraper_config = config.get("SCRAPER", {})
    min_delay = scraper_config.get("MIN_REQUEST_DELAY", 1.0)
    domain = urlparse(url).netloc
    if domain in _request_history and (time.time() - _request_history[domain]) < min_delay:
        await asyncio.sleep(min_delay - (time.time() - _request_history[domain]))
    _request_history[domain] = time.time()

    client = get_shared_async_client()
    for attempt in range(attempts):
        try:
            headers = random.choice(FINGERPRINTS).copy()
            if scraper_config.get("ENABLE_STEALTH_HEADERS"):
                headers.update(STEALTH_HEADERS)
            if scraper_config.get("ENABLE_CACHE_BUST"):
                headers.update(CACHE_BUST_HEADERS)

            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response
        except Exception as e:
            logging.warning(f"Fetch attempt {attempt + 1} for {url} failed: {e}")
            client = get_shared_async_client(fresh_session=True)
            await asyncio.sleep((attempt + 1) * 2)
    raise FetchingError(f"Failed to fetch {url} after {attempts} attempts.")


# =============================================================================
# --- ADAPTERS ---
# =============================================================================
class BaseV2Adapter:
    source_id: str = "base_adapter"

    def __init__(self, config: dict):
        self.config = config
        self.site_config = config.get("DATA_SOURCES_V2", {}).get(self.source_id)

    async def fetch(self) -> list[RawRaceDocument]:
        raise NotImplementedError


@register_adapter
class TimeformAdapter(BaseV2Adapter):
    source_id = "timeform"

    async def fetch(self) -> list[RawRaceDocument]:
        if not self.site_config or not self.site_config.get("enabled"):
            return []
        await resilient_get(self.site_config["url"], self.config)
        # Simplified parsing for demo
        return []


@register_adapter
class SportingLifeAdapter(BaseV2Adapter):
    source_id = "sportinglife"

    async def fetch(self) -> list[RawRaceDocument]:
        if not self.site_config or not self.site_config.get("enabled"):
            return []
        url = self.site_config["url"].format(date_str_iso=date.today().isoformat())
        await resilient_get(url, self.config)
        # Simplified parsing for demo
        return []


# ... Other placeholder adapters ...


# =============================================================================
# --- ANALYSIS & MAIN LOGIC ---
# =============================================================================
class V2Scorer:
    """
    Analyzes a NormalizedRace to produce a score based on various signals.
    Weights are now loaded from the configuration file for easy tuning.
    """

    def __init__(self, config: Dict):
        # --- Main Scorer Weights ---
        default_weights = {
            "FIELD_SIZE": 0.25,
            "FAVORITE_ODDS": 0.35,
            "ODDS_SPREAD": 0.10,
            "VALUE_VS_SP": 0.30,
        }
        scorer_weights = config.get("SCORER_WEIGHTS", default_weights)
        for key, value in default_weights.items():
            if key not in scorer_weights:
                scorer_weights[key] = value
                logging.warning(f"Missing '{key}' in SCORER_WEIGHTS, using default: {value}")

        total_weight = sum(scorer_weights.values())
        self.weights = (
            {k: v / total_weight for k, v in scorer_weights.items()}
            if total_weight
            else default_weights
        )
        logging.info(f"V2Scorer initialized with main weights: {self.weights}")

        # --- Best Value Scorer Weights ---
        default_value_weights = {"VALUE_ODDS_WEIGHT": 0.6, "VALUE_COMPETITIVENESS_WEIGHT": 0.4}
        value_weights = config.get("BEST_VALUE_WEIGHTS", default_value_weights)
        for key, value in default_value_weights.items():
            if key not in value_weights:
                value_weights[key] = value
                logging.warning(f"Missing '{key}' in BEST_VALUE_WEIGHTS, using default: {value}")

        total_value_weight = sum(value_weights.values())
        self.value_weights = (
            {k: v / total_value_weight for k, v in value_weights.items()}
            if total_value_weight
            else default_value_weights
        )
        logging.info(f"V2Scorer initialized with value weights: {self.value_weights}")

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
            return 20.0
        if fav_odds < 1.5:
            return 60.0
        if 1.5 <= fav_odds < 2.5:
            return 100.0
        if 2.5 <= fav_odds < 4.0:
            return 80.0
        if 4.0 <= fav_odds < 6.0:
            return 50.0
        return 30.0

    def _get_odds_spread_score(
        self, fav_odds: Optional[float], sec_fav_odds: Optional[float]
    ) -> float:
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
        if len(runners) < 3:
            return 20.0, 0.0
        fav_odds = runners[0].odds_decimal
        avg_odds = sum(r.odds_decimal for r in runners) / len(runners)
        if avg_odds == 0:
            return 0.0, 0.0
        ratio = fav_odds / avg_odds
        if ratio >= 0.8:
            return 100.0, ratio
        if 0.7 <= ratio < 0.8:
            return 90.0, ratio
        if 0.5 <= ratio < 0.7:
            return 70.0, ratio
        if 0.3 <= ratio < 0.5:
            return 50.0, ratio
        return 40.0, ratio

    def _get_best_value_score(
        self, runners_with_odds: list
    ) -> tuple[Optional[float], Optional[str]]:
        """
        Calculates a 'Best Value' score by identifying a horse (3rd favorite)
        that has a good combination of high odds and competitiveness.
        """
        if len(runners_with_odds) < 3:
            return None, "Not enough runners for value score."

        fav_horse = runners_with_odds[0]
        value_horse = runners_with_odds[2]  # Target the 3rd favorite as the "value horse"

        value_horse_odds = value_horse.odds_decimal
        fav_odds = fav_horse.odds_decimal

        if value_horse_odds is None or fav_odds is None:
            return None, "Odds missing for value calculation."

        # 1. Score based on the horse's odds (the "value" part)
        if 5.0 <= value_horse_odds < 10.0:
            value_odds_score = 100.0
        elif 10.0 <= value_horse_odds < 15.0:
            value_odds_score = 80.0
        elif 3.0 <= value_horse_odds < 5.0:
            value_odds_score = 50.0
        elif value_horse_odds >= 15.0:
            value_odds_score = 20.0
        else:
            value_odds_score = 0.0  # Odds < 3.0 is not a value bet

        # 2. Score based on competitiveness vs favorite
        spread = value_horse_odds - fav_odds
        if spread < 4.0:
            competitiveness_score = 100.0
        elif 4.0 <= spread < 8.0:
            competitiveness_score = 70.0
        else:
            competitiveness_score = 30.0

        # 3. Calculate final weighted score
        final_value_score = (value_odds_score * self.value_weights["VALUE_ODDS_WEIGHT"]) + (
            competitiveness_score * self.value_weights["VALUE_COMPETITIVENESS_WEIGHT"]
        )

        reason = f"Value Pick: {value_horse.name} ({value_horse_odds:.2f})"
        return round(final_value_score, 2), reason

    def score_race(self, race: NormalizedRace) -> ScoreResult:
        """Calculates a score for a single normalized race."""
        runners_with_odds = sorted(
            [r for r in race.runners if r.odds_decimal is not None], key=lambda r: r.odds_decimal
        )

        if len(runners_with_odds) < 2:
            return ScoreResult(race=race, score=0.0, reason="Not enough runners with odds.")

        favorite = runners_with_odds[0]
        second_favorite = runners_with_odds[1]
        fav_odds = favorite.odds_decimal
        sec_fav_odds = second_favorite.odds_decimal
        field_size = len(race.runners)

        # Calculate main component scores
        field_size_score = self._get_field_size_score(field_size)
        fav_odds_score = self._get_fav_odds_score(fav_odds)
        spread_score = self._get_odds_spread_score(fav_odds, sec_fav_odds)
        fav_ratio_score, fav_ratio = self._get_fav_vs_field_ratio_score(runners_with_odds)

        final_score = (
            (field_size_score * self.weights["FIELD_SIZE"])
            + (fav_odds_score * self.weights["FAVORITE_ODDS"])
            + (spread_score * self.weights["ODDS_SPREAD"])
            + (fav_ratio_score * self.weights["VALUE_VS_SP"])
        )
        reason = (
            f"Field: {field_size} ({field_size_score:.0f}), "
            f"Fav Odds: {fav_odds:.2f} ({fav_odds_score:.0f}), "
            f"Spread: {(sec_fav_odds - fav_odds):.2f} ({spread_score:.0f}), "
            f"FavRatio: {fav_ratio:.2f}({fav_ratio_score:.0f})"
        )

        # Calculate best value score
        best_value_score, best_value_reason = self._get_best_value_score(runners_with_odds)

        return ScoreResult(
            race=race,
            score=round(final_score, 2),
            reason=reason,
            best_value_score=best_value_score,
            best_value_reason=best_value_reason,
        )


def score_races(races: List[NormalizedRace], config: Dict) -> List[ScoreResult]:
    scorer = V2Scorer(config)
    return sorted([scorer.score_race(race) for race in races], key=lambda r: r.score, reverse=True)


def generate_paddock_reports(scored_results: List[ScoreResult], config: Dict):
    """
    Generates JSON and HTML reports from a list of scored race results.
    """
    output_dir = Path(config["DEFAULT_OUTPUT_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)
    today_str = date.today().strftime("%Y-%m-%d")

    # JSON Report
    json_path = output_dir / f"paddock_report_v2_{today_str}.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump([asdict(res) for res in scored_results], f, indent=2)
        logging.info(f"V2 JSON report saved to {json_path}")
    except Exception as e:
        logging.error(f"Failed to save V2 JSON report: {e}")

    # HTML Report
    html_path = output_dir / f"paddock_report_v2_{today_str}.html"
    try:
        env = Environment(loader=FileSystemLoader("."), autoescape=select_autoescape())
        template = env.get_template(config["TEMPLATE_PADDOCK"])
        html_output = template.render(races=scored_results, config=config, report_date=today_str)
        html_path.write_text(html_output, encoding="utf-8")
        logging.info(f"V2 HTML report saved to {html_path}")
    except Exception as e:
        logging.error(f"Failed to generate V2 HTML report: {e}")


async def run_unified_pipeline(config: Dict, args: Optional[argparse.Namespace]):
    logging.info("--- Starting Unified Analysis Pipeline ---")
    enabled_adapters = [
        adapter(config)
        for adapter in ADAPTERS
        if adapter(config).site_config and adapter(config).site_config.get("enabled")
    ]
    adapter_results = await asyncio.gather(
        *(adapter.fetch() for adapter in enabled_adapters), return_exceptions=True
    )
    raw_docs = [doc for res in adapter_results if isinstance(res, list) for doc in res]

    races_by_key = {
        key: list(group)
        for key, group in groupby(
            sorted(raw_docs, key=attrgetter("race_key")), key=attrgetter("race_key")
        )
    }
    normalized_races = [
        normalize_race_docs(docs[0]) for docs in races_by_key.values()
    ]  # Simplified merge

    scored_results = score_races(normalized_races, config)

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
        sorted_runners = sorted(
            result.race.runners,
            key=lambda r: int(r.saddle_cloth) if r.saddle_cloth.isdigit() else 999,
        )
        for runner in sorted_runners:
            odds = f"{runner.odds_decimal:.2f}" if runner.odds_decimal else "N/A"
            print(f"    - {runner.saddle_cloth}. {runner.name} ({odds})")

    # Also generate the reports
    generate_paddock_reports(scored_results, config)
    print("✅ Unified analysis pipeline complete.")


# =============================================================================
# --- EXECUTION GUARD ---
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main_config = load_config()
    if not main_config:
        sys.exit("Could not load configuration. Exiting.")

    parser = argparse.ArgumentParser(description="Paddock Parser Toolkit - Portable Demo")
    parser.add_argument(
        "command", nargs="?", default="analyze", help="The command to run (default: analyze)"
    )
    args = parser.parse_args()

    if args.command == "analyze":
        asyncio.run(run_unified_pipeline(main_config, args))
    else:
        print(f"Unknown command: {args.command}")
