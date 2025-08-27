#!/usr/bin/env python3
"""
Paddock Parser v2.0 - UNIFIED

---
This module, formerly the V1 "Deep Dive" tool, has been fully upgraded to
integrate with the V2 data pipeline. It retains its core philosophy of
reliability through manual/batch workflows but now uses the unified V2 data
model (`NormalizedRace`) and the `V2Scorer` for consistent analysis across
the entire toolkit.
---
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

# Import the advanced parser provided by the team
try:
    from racing_data_parser import RacingDataParser
except ImportError:
    print("FATAL: Could not import racing_data_parser.py. Ensure it's in the same directory.", file=sys.stderr)
    sys.exit(1)

# Shared Intelligence: V2 Data Models, Scorers, and Normalizers
try:
    from normalizer import (
        NormalizedRace,
        NormalizedRunner,
        convert_odds_to_decimal,
        canonical_track_key,
        canonical_race_key,
    )
    from analysis import V2Scorer, ScoreResult
except ImportError:
    print("FATAL: Could not import key V2 modules (normalizer, analysis). Ensure they are present.", file=sys.stderr)
    sys.exit(1)


# =============================================================================
# --- V1 to V2 DATA CONVERSION & MERGING ---
# =============================================================================

def convert_v1_dict_to_v2_race(race_dict: Dict[str, Any]) -> Optional[NormalizedRace]:
    """
    Converts a dictionary from the V1 RacingDataParser into a V2 NormalizedRace.
    This acts as the bridge between the legacy parser output and the modern data model.
    """
    try:
        # --- Key Generation ---
        track_key = canonical_track_key(race_dict["course"])
        time_str = race_dict["race_time"].replace(":", "")
        race_key = canonical_race_key(track_key, time_str)

        # --- Runner Normalization ---
        normalized_runners = []
        for i, runner_dict in enumerate(race_dict.get("runners", [])):
            runner_name = runner_dict.get("name")
            if not runner_name:
                continue

            # V1 parser doesn't provide saddle cloth; generate a placeholder.
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

        # --- Race Normalization ---
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
    # Merge runners, preferring runners with odds over those without.
    existing_runners_map = {r.name: r for r in existing_race.runners}
    for new_runner in new_race.runners:
        if new_runner.name in existing_runners_map:
            existing_runner = existing_runners_map[new_runner.name]
            if new_runner.odds_decimal is not None and existing_runner.odds_decimal is None:
                existing_runners_map[new_runner.name] = new_runner
        else:
            existing_runners_map[new_runner.name] = new_runner
    existing_race.runners = list(existing_runners_map.values())

    # Combine source_ids without duplicates.
    existing_race.source_ids = sorted(list(set(existing_race.source_ids) | set(new_race.source_ids)))

    # Fill in missing extras from the new race.
    for key, value in new_race.extras.items():
        if key not in existing_race.extras or existing_race.extras[key] is None:
            existing_race.extras[key] = value

    return existing_race

# =============================================================================
# --- PERSISTENT ENGINE (V2 INTEGRATED) ---
# =============================================================================
def run_persistent_engine(config: Dict, args: argparse.Namespace):
    """
    Runs the main, always-on loop. It listens for clipboard data, converts it
    to the V2 data model, and merges it into a daily cache.
    """
    logging.info("Starting Persistent Engine (V2 Unified)...")
    scorer = V2Scorer(config)
    parser = RacingDataParser()

    cache_dir = Path(args.cache_dir or config["DEFAULT_OUTPUT_DIR"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    today_str = date.today().strftime("%Y-%m-%d")
    cache_file = cache_dir / f"paddock_cache_v2_{today_str}.json"

    races_by_key: Dict[str, NormalizedRace] = {}
    if cache_file.exists() and not args.disable_cache_backup:
        restore = args.auto_restore or input(f"Cache file found for today. Restore? (Y/n): ").strip().lower() in ['y', '']
        if restore:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    for race_dict in cached_data:
                        races_by_key[race_dict['race_key']] = NormalizedRace(**race_dict)
                logging.info(f"Loaded {len(races_by_key)} races from V2 cache: {cache_file}")
            except (json.JSONDecodeError, TypeError) as e:
                logging.warning(f"Cache file '{cache_file}' is corrupted. Starting fresh. Error: {e}")

    logging.info(f"Engine running. Paste data, then type '{args.paste_sentinel}' and Enter.")

    try:
        while True:
            print(f"\nPaste content, then type '{args.paste_sentinel}' and press Enter.")
            lines = sys.stdin.read().split(args.paste_sentinel)
            pasted_content = lines[0]

            if not pasted_content.strip():
                continue

            parsed_dicts = parser.parse_racing_data(pasted_content, "Clipboard Paste")
            if not parsed_dicts:
                logging.warning("No races parsed from pasted content.")
                continue

            update_count, new_count = 0, 0
            for race_dict in parsed_dicts:
                new_race = convert_v1_dict_to_v2_race(race_dict)
                if not new_race:
                    continue

                if new_race.race_key in races_by_key:
                    existing_race = races_by_key[new_race.race_key]
                    races_by_key[new_race.race_key] = merge_normalized_races(existing_race, new_race)
                    update_count += 1
                else:
                    races_by_key[new_race.race_key] = new_race
                    new_count += 1

            logging.info(f"Processed paste. Added {new_count} new, updated {update_count} existing.")

            # Save cache atomically after each paste
            if not args.disable_cache_backup:
                temp_file = cache_file.with_suffix('.json.tmp')
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump([asdict(race) for race in races_by_key.values()], f, indent=2)
                temp_file.rename(cache_file)
                logging.info(f"Cache for {len(races_by_key)} races saved to {cache_file}")

    except KeyboardInterrupt:
        logging.info("\nExiting persistent engine.")
    except Exception as e:
        logging.critical(f"Critical error in persistent engine: {e}", exc_info=True)

# =============================================================================
# --- BATCH PARSE MODE (V2 INTEGRATED) ---
# =============================================================================

def parse_local_files(config: Dict, args: Optional[argparse.Namespace]) -> List[NormalizedRace]:
    """
    Parses all local HTML files from the input directory, converts them to
    NormalizedRace objects, and returns them as a list.
    """
    input_dir_str = None
    # Handle cases where args might be None or the attribute might not be set
    if args and hasattr(args, 'input_dir') and args.input_dir:
        input_dir_str = args.input_dir
    else:
        input_dir_str = config.get("INPUT_DIR", "html_input")

    input_path = Path(input_dir_str)

    # Automatically create the directory if it doesn't exist.
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
        with open(json_path, 'w', encoding='utf-8') as f:
            # Use asdict to convert the list of dataclasses to dicts
            json.dump([asdict(res) for res in scored_results], f, indent=2)
        logging.info(f"V2 JSON report saved to {json_path}")
    except Exception as e:
        logging.error(f"Failed to save V2 JSON report: {e}")

    # HTML Report
    html_path = output_dir / f"paddock_report_v2_{today_str}.html"
    try:
        env = Environment(loader=FileSystemLoader('.'), autoescape=select_autoescape())
        template = env.get_template(config["TEMPLATE_PADDOCK"])
        html_output = template.render(races=scored_results, config=config, report_date=today_str)
        html_path.write_text(html_output, encoding='utf-8')
        logging.info(f"V2 HTML report saved to {html_path}")
    except Exception as e:
        logging.error(f"Failed to generate V2 HTML report: {e}")


def run_batch_parse(config: Dict, args: Optional[argparse.Namespace]):
    """
    Standalone function to run the complete batch parse workflow:
    Parse local files -> Score -> Generate Reports.
    """
    logging.info("Running standalone batch parse workflow...")

    # 1. Parse local files
    normalized_races = parse_local_files(config, args)
    if not normalized_races:
        logging.warning("Batch parsing yielded no races. Exiting.")
        return

    # 2. Score the races
    scorer = V2Scorer(config)
    scored_results = [scorer.score_race(race) for race in normalized_races]
    sorted_results = sorted(scored_results, key=lambda r: r.score, reverse=True)

    # 3. Generate reports
    generate_paddock_reports(sorted_results, config)

    logging.info("Batch parsing workflow complete.")


if __name__ == "__main__":
    print("This script is intended to be run via main.py")
    print("Example: python main.py parse")
    print("Example: python main.py persistent")
