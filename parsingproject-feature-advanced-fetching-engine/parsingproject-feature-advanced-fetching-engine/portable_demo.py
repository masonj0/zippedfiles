# =============================================================================
# --- HEADER ---
# =============================================================================
"""
Paddock Parser Toolkit v2.1 - Portable Demo Version

This is a single-file, portable version of the Paddock Parser Toolkit.
It consolidates all the application's logic into one file for easy sharing
and demonstration. This version includes the advanced fetching module.

To run this file, you need to have the following dependencies installed:
pip install nest_asyncio httpx beautifulsoup4 curl_cffi jinja2 tqdm pytz

You also need a `config_settings.json` file in the same directory.
"""

# =============================================================================
# --- IMPORTS ---
# =============================================================================
import nest_asyncio
nest_asyncio.apply()

import sys
import logging
import asyncio
import argparse
import json
import re
import ssl
import random
import webbrowser
import hashlib
import unicodedata
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Protocol, Type
from dataclasses import dataclass, field, asdict
from itertools import groupby
from operator import attrgetter
from urllib.parse import quote, urlparse, urljoin
from datetime import date, datetime, timezone

try:
    import httpx
    from bs4 import BeautifulSoup, Tag
    from curl_cffi.requests import AsyncSession, RequestsError
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from tqdm import tqdm
    import pytz
    import certifi
except ImportError as e:
    print(f"FATAL: Missing required dependency: {e.name}", file=sys.stderr)
    print("Please install requirements: pip install nest_asyncio httpx beautifulsoup4 curl_cffi jinja2 tqdm pytz certifi", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# --- CONFIGURATION LOADER ---
# =============================================================================
def load_config(path: str = 'config_settings.json') -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
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
    value: Any; confidence: float; source: str

@dataclass
class RunnerDoc:
    runner_id: str; name: FieldConfidence; number: FieldConfidence
    odds: Optional[FieldConfidence] = None; jockey: Optional[FieldConfidence] = None
    trainer: Optional[FieldConfidence] = None; extras: Dict[str, FieldConfidence] = field(default_factory=dict)

@dataclass
class RawRaceDocument:
    source_id: str; fetched_at: str; track_key: str; race_key: str
    start_time_iso: str; runners: List[RunnerDoc]; extras: Dict[str, FieldConfidence] = field(default_factory=dict)

@dataclass
class NormalizedRunner:
    runner_id: str; name: str; saddle_cloth: str
    odds_decimal: Optional[float] = None; odds_fractional: Optional[str] = None
    jockey_name: Optional[str] = None; trainer_name: Optional[str] = None
    confidence_scores: Dict[str, float] = field(default_factory=dict); raw_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NormalizedRace:
    race_key: str; track_key: str; start_time_iso: str
    race_name: Optional[str] = None; going: Optional[str] = None
    runners: List[NormalizedRunner] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list); extras: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScoreResult:
    race: NormalizedRace; score: float; reason: str

class SourceAdapter(Protocol):
    source_id: str
    def __init__(self, config: Dict[str, Any]): ...
    async def fetch(self) -> List[RawRaceDocument]: ...

def register_adapter(cls: Type[SourceAdapter]) -> Type[SourceAdapter]:
    if not hasattr(cls, "source_id"): raise TypeError(f"Adapter {cls.__name__} must have a 'source_id' attribute.")
    if cls not in ADAPTERS:
        logging.info(f"Registering adapter: {cls.__name__} for source '{cls.source_id}'")
        ADAPTERS.append(cls)
    return cls

# =============================================================================
# --- NORMALIZER FUNCTIONS ---
# =============================================================================
def canonical_track_key(name: str) -> str:
    if not name: return "unknown_track"
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    return re.sub(r'[\s-]+', '_', name)

def canonical_race_key(track_key: str, race_time: str) -> str:
    return f"{track_key}::r{re.sub(r'[^0-9]', '', race_time)}"

def normalize_course_name(name: str) -> str:
    # Simplified for demo
    return name.lower().strip()

def map_discipline(discipline_name: str) -> str:
    d_lower = discipline_name.lower()
    if "greyhound" in d_lower: return "greyhound"
    if "harness" in d_lower: return "harness"
    return "thoroughbred"

def parse_hhmm_any(time_text: str) -> Optional[str]:
    if not time_text: return None
    match = re.search(r'(\d{1,2})[:.](\d{2})', str(time_text))
    if not match: return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if 'pm' in str(time_text).lower() and hour != 12: hour += 12
    if 'am' in str(time_text).lower() and hour == 12: hour = 0
    return f"{hour:02d}:{minute:02d}"

def convert_odds_to_decimal(odds_str: str) -> Optional[float]:
    if not isinstance(odds_str, str) or not odds_str.strip(): return None
    s = odds_str.strip().upper().replace("-", "/")
    if s in {"SP", "NR", "SCR", "VOID"}: return None
    if s in {"EVS", "EVENS"}: return 2.0
    if "/" in s:
        try:
            num, den = map(float, s.split("/", 1))
            return (num / den) + 1.0 if den > 0 else None
        except (ValueError, ZeroDivisionError): return None
    try: return float(s) if float(s) > 1.0 else None
    except ValueError: return None

def normalize_race_docs(doc: RawRaceDocument) -> NormalizedRace:
    runners = [NormalizedRunner(runner_id=r.runner_id, name=r.name.value, saddle_cloth=r.number.value, odds_decimal=convert_odds_to_decimal(r.odds.value if r.odds else None), odds_fractional=r.odds.value if r.odds else None) for r in doc.runners]
    return NormalizedRace(race_key=doc.race_key, track_key=doc.track_key, start_time_iso=doc.start_time_iso, runners=runners, source_ids=[doc.source_id], extras={k: v.value for k, v in doc.extras.items()})

# =============================================================================
# --- ADVANCED FETCHER ---
# =============================================================================
class FetchingError(Exception): pass
class BlockingDetectedError(FetchingError): pass

_shared_async_client: Optional[httpx.AsyncClient] = None
_request_history: Dict[str, float] = {}

def get_shared_async_client(fresh_session: bool = False) -> httpx.AsyncClient:
    global _shared_async_client
    if _shared_async_client is None or _shared_async_client.is_closed or fresh_session:
        if _shared_async_client and not _shared_async_client.is_closed:
            asyncio.create_task(_shared_async_client.aclose())
        headers = random.choice(FINGERPRINTS).copy()
        _shared_async_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0, headers=headers, verify=certifi.where())
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
            if scraper_config.get("ENABLE_STEALTH_HEADERS"): headers.update(STEALTH_HEADERS)
            if scraper_config.get("ENABLE_CACHE_BUST"): headers.update(CACHE_BUST_HEADERS)

            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response
        except Exception as e:
            logging.warning(f"Fetch attempt {attempt+1} for {url} failed: {e}")
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
    async def fetch(self) -> list[RawRaceDocument]: raise NotImplementedError

@register_adapter
class TimeformAdapter(BaseV2Adapter):
    source_id = "timeform"
    async def fetch(self) -> list[RawRaceDocument]:
        if not self.site_config or not self.site_config.get("enabled"): return []
        list_response = await resilient_get(self.site_config["url"], self.config)
        soup = BeautifulSoup(list_response.text, "html.parser")
        # Simplified parsing for demo
        return []

@register_adapter
class SportingLifeAdapter(BaseV2Adapter):
    source_id = "sportinglife"
    async def fetch(self) -> list[RawRaceDocument]:
        if not self.site_config or not self.site_config.get("enabled"): return []
        url = self.site_config["url"].format(date_str_iso=date.today().isoformat())
        response = await resilient_get(url, self.config)
        # Simplified parsing for demo
        return []

# ... Other placeholder adapters ...

# =============================================================================
# --- ANALYSIS & MAIN LOGIC ---
# =============================================================================
class V2Scorer:
    def __init__(self, config: Dict):
        self.weights = config.get("SCORER_WEIGHTS", {})
    def score_race(self, race: NormalizedRace) -> ScoreResult:
        # Simplified scoring for demo
        score = len(race.runners) * 10
        return ScoreResult(race=race, score=score, reason="Demo score")

def score_races(races: List[NormalizedRace], config: Dict) -> List[ScoreResult]:
    scorer = V2Scorer(config)
    return sorted([scorer.score_race(race) for race in races], key=lambda r: r.score, reverse=True)

async def run_unified_pipeline(config: Dict, args: Optional[argparse.Namespace]):
    logging.info("--- Starting Unified Analysis Pipeline ---")
    enabled_adapters = [adapter(config) for adapter in ADAPTERS if adapter(config).site_config and adapter(config).site_config.get("enabled")]
    adapter_results = await asyncio.gather(*(adapter.fetch() for adapter in enabled_adapters), return_exceptions=True)
    raw_docs = [doc for res in adapter_results if isinstance(res, list) for doc in res]

    races_by_key = {key: list(group) for key, group in groupby(sorted(raw_docs, key=attrgetter("race_key")), key=attrgetter("race_key"))}
    normalized_races = [normalize_race_docs(docs[0]) for docs in races_by_key.values()] # Simplified merge

    scored_results = score_races(normalized_races, config)
    for result in scored_results:
        print(f"Race: {result.race.race_key}, Score: {result.score}")

# =============================================================================
# --- EXECUTION GUARD ---
# =============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main_config = load_config()
    if not main_config:
        sys.exit("Could not load configuration. Exiting.")

    parser = argparse.ArgumentParser(description="Paddock Parser Toolkit - Portable Demo")
    parser.add_argument('command', nargs='?', default='analyze', help="The command to run (default: analyze)")
    args = parser.parse_args()

    if args.command == 'analyze':
        asyncio.run(run_unified_pipeline(main_config, args))
    else:
        print(f"Unknown command: {args.command}")
