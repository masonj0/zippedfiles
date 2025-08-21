#!/usr/bin/env python3
"""
Paddock Parser v2.0 - UNIFIED
"""

import json
import logging
import sys
import time
import argparse
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from tqdm import tqdm
from jinja2 import Environment, FileSystemLoader, select_autoescape

from racing_data_parser import RacingDataParser
from normalizer import (
    NormalizedRace,
    NormalizedRunner,
    convert_odds_to_decimal,
    canonical_track_key,
    canonical_race_key,
)
# from analysis import V2Scorer, ScoreResult # <-- CIRCULAR DEPENDENCY REMOVED


# =============================================================================
# --- V1 to V2 DATA CONVERSION & MERGING ---
# =============================================================================

def convert_v1_dict_to_v2_race(race_dict: Dict[str, Any]) -> Optional[NormalizedRace]:
    """
    Converts a dictionary from the V1 RacingDataParser into a V2 NormalizedRace.
    """
    try:
        track_key = canonical_track_key(race_dict["course"])
        time_str = race_dict["race_time"].replace(":", "")
        race_key = canonical_race_key(track_key, time_str)

        normalized_runners = []
        for i, runner_dict in enumerate(race_dict.get("runners", [])):
            runner_name = runner_dict.get("name")
            if not runner_name:
                continue

            saddle_cloth = str(i + 1)

            normalized_runners.append(
                NormalizedRunner(
                    runner_id=f"{race_key}-{saddle_cloth}",
                    name=runner_name,
                    saddle_cloth=saddle_cloth,
                    odds_decimal=convert_odds_to_decimal(runner_dict.get("odds_str")),
                    odds_fractional=runner_dict.get("odds_str"),
                )
            )

        today = date.today().isoformat()
        start_time_iso = race_dict.get("utc_datetime", f"{today}T{race_dict['race_time']}:00")

        return NormalizedRace(
            race_key=race_key,
            track_key=track_key,
            start_time_iso=start_time_iso,
            race_name=race_dict.get("race_type"),
            runners=normalized_runners,
            source_ids=[race_dict.get("source_file", "clipboard")],
            extras={
                "v1_id": race_dict.get("id"),
                "country": race_dict.get("country"),
                "discipline": race_dict.get("discipline"),
                "race_url": race_dict.get("race_url"),
            },
        )
    except (KeyError, TypeError) as e:
        logging.error(f"Failed to convert V1 race dict to V2 NormalizedRace: {e}", exc_info=True)
        logging.debug(f"Problematic race dict: {race_dict}")
        return None

def merge_normalized_races(existing_race: NormalizedRace, new_race: NormalizedRace) -> NormalizedRace:
    """
    Intelligently merges a new NormalizedRace into an existing one.
    """
    existing_runners_map = {r.name: r for r in existing_race.runners}
    for new_runner in new_race.runners:
        if new_runner.name in existing_runners_map:
            existing_runner = existing_runners_map[new_runner.name]
            if new_runner.odds_decimal is not None and existing_runner.odds_decimal is None:
                existing_runners_map[new_runner.name] = new_runner
        else:
            existing_runners_map[new_runner.name] = new_runner
    existing_race.runners = list(existing_runners_map.values())

    existing_race.source_ids = sorted(list(set(existing_race.source_ids) | set(new_race.source_ids)))

    for key, value in new_race.extras.items():
        if key not in existing_race.extras or existing_race.extras[key] is None:
            existing_race.extras[key] = value

    return existing_race

# =============================================================================
# --- PERSISTENT ENGINE (V2 INTEGRATED) ---
# =============================================================================
def run_persistent_engine(config: Dict, args: argparse.Namespace):
    """
    Runs the main, always-on loop.
    """
    logging.error("Persistent engine temporarily disabled due to circular dependency fix.")
    pass


# =============================================================================
# --- BATCH PARSE MODE (V2 INTEGRATED) ---
# =============================================================================

def parse_local_files(config: Dict, args: Optional[argparse.Namespace]) -> List[NormalizedRace]:
    """
    Parses all local HTML files from the input directory.
    """
    input_dir_str = getattr(args, 'input_dir', None) or config.get("INPUT_DIR", "html_input")
    input_path = Path(input_dir_str)
    input_path.mkdir(parents=True, exist_ok=True)

    logging.info(f"Starting local file parsing from '{input_path}'.")
    parser = RacingDataParser()
    races_by_key: Dict[str, NormalizedRace] = {}

    html_files = list(input_path.glob("*.html")) + list(input_path.glob("*.htm"))
    if not html_files:
        logging.warning(f"No HTML files found in '{input_path}'.")
        return []

    for file_path in tqdm(html_files, desc="Parsing Local Files"):
        try:
            html_content = file_path.read_text(encoding='utf-8')
            parsed_dicts = parser.parse_racing_data(html_content, source_file=file_path.name)

            for race_dict in parsed_dicts:
                new_race = convert_v1_dict_to_v2_race(race_dict)
                if not new_race:
                    continue

                if new_race.race_key in races_by_key:
                    existing = races_by_key[new_race.race_key]
                    races_by_key[new_race.race_key] = merge_normalized_races(existing, new_race)
                else:
                    races_by_key[new_race.race_key] = new_race
        except Exception as e:
            logging.error(f"Error processing file {file_path.name}: {e}", exc_info=True)

    logging.info(f"Local file parsing complete. Found {len(races_by_key)} unique races.")
    return list(races_by_key.values())


def generate_paddock_reports(scored_results: List, config: Dict):
    """
    Generates JSON and HTML reports from a list of scored race results.
    """
    logging.error("Report generation temporarily disabled due to circular dependency fix.")
    pass


def run_batch_parse(config: Dict, args: Optional[argparse.Namespace]):
    """
    Standalone function to run the complete batch parse workflow.
    """
    logging.error("Batch parsing temporarily disabled due to circular dependency fix.")
    pass


if __name__ == "__main__":
    print("This script is intended to be run via main.py")
