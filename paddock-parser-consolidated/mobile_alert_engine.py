#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Mobile Alerting Engine v1.3

This is a standalone, continuously running service designed for Termux on Android.
It autonomously scans for high-value racing opportunities and sends proactive
notifications to the device.
"""

import os
import sys
import json
import logging
import asyncio
import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Any, Set
from aiohttp import web
from bs4 import BeautifulSoup

# Global flag for webhook trigger
SCAN_NOW = False

# --- Shared Intelligence Imports ---
# This script assumes the paddock_parser package is installed (e.g., pip install -e .)
try:
    from paddock_parser.normalizer import (
        NormalizedRace,
        NormalizedRunner,
        normalize_course_name,
        parse_hhmm_any,
        convert_odds_to_fractional_decimal,
        canonical_track_key,
        canonical_race_key,
    )
    from paddock_parser.analysis import V2Scorer
    from paddock_parser.fetching import resilient_get, close_shared_async_client
    from paddock_parser.spectral_scheduler import run_bursts, safe_async_run
except ImportError as e:
    print(
        "FATAL: Could not import paddock_parser modules. Ensure the package is installed.",
        file=sys.stderr,
    )
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# --- CONFIGURATION & LOGGING ---
# =============================================================================


def load_config(path: str = "mobile_config.json") -> Dict[str, Any]:
    """Loads the mobile-specific configuration file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.critical(f"FATAL: Could not load or parse '{path}'. Error: {e}")
        sys.exit(1)
    return {}


def setup_logging(log_file: str):
    """Configures logging for the mobile application."""
    log_dir = Path(log_file).parent
    log_dir.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file, mode="w"), logging.StreamHandler(sys.stdout)],
        force=True,
    )


# =============================================================================
# --- CORE DATA & STATE MANAGEMENT ---
# =============================================================================


def generate_race_id(course: str, race_date: date, time: str) -> str:
    """Creates a unique, deterministic ID for a race."""
    key = f"{normalize_course_name(course)}|{race_date.isoformat()}|{re.sub(r'[^\d]', '', time or '')}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def load_alert_state(state_file_path: Path) -> Set[str]:
    """Loads the set of already-alerted race IDs from the state file."""
    if not state_file_path.exists():
        return set()
    try:
        with open(state_file_path, "r", encoding="utf-8") as f:
            # Check if the file is empty before trying to load JSON
            content = f.read()
            if not content:
                return set()
            return set(json.loads(content))
    except (json.JSONDecodeError, TypeError):
        logging.warning(f"Could not parse state file '{state_file_path}'. Starting fresh.")
        return set()


def save_alert_state(state_file_path: Path, alerted_ids: Set[str]):
    """Saves the set of alerted race IDs to the state file."""
    try:
        with open(state_file_path, "w", encoding="utf-8") as f:
            json.dump(list(alerted_ids), f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save alert state to '{state_file_path}': {e}")


# =============================================================================
# --- WEBHOOK & NOTIFICATION HELPERS ---
# =============================================================================


async def trigger_scan(request):
    """Webhook handler to trigger an immediate scan."""
    global SCAN_NOW
    SCAN_NOW = True
    return web.Response(text="ok")


async def maybe_start_webhook(config: Dict[str, Any]):
    """Starts the aiohttp webhook server if enabled in the config."""
    WH = config.get("Webhook", {})
    if not WH.get("enabled"):
        return None
    app = web.Application()
    app.add_routes([web.post(WH.get("path", "/trigger"), trigger_scan)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WH.get("host", "0.0.0.0"), WH.get("port", 8765))
    await site.start()
    logging.info(
        f"Webhook server started on http://{WH.get('host', '0.0.0.0')}:{WH.get('port', 8765)}{WH.get('path', '/trigger')}"
    )
    return runner


def format_reasons(score_result, meta=None):
    """Formats score reasons for notifications, adding metadata like DNS divergence."""
    parts = []
    # Assuming score_result has a 'reasons' attribute which is a list of strings
    if hasattr(score_result, "reasons") and score_result.reasons:
        parts.extend(score_result.reasons[:2])
    if meta and meta.get("dns_divergence"):
        parts.append("dns-divergence")
    return " | ".join(parts)


def send_termux_notification(title: str, content: str):
    """
    Uses the Termux API to send a native Android notification.
    """
    logging.info(f"Sending Notification: '{title}' - '{content}'")
    try:
        # Sanitize inputs to prevent command injection issues
        safe_title = json.dumps(title)
        safe_content = json.dumps(content)
        command = f"termux-notification --title {safe_title} --content {safe_content}"
        os.system(command)
    except Exception as e:
        logging.error(f"Failed to send Termux notification: {e}")


# =============================================================================
# --- DATA ACQUISITION & PARSING ---
# =============================================================================


def parse_source(html_content: str, source_name: str) -> List[NormalizedRace]:
    """
    A simplified parser for the mobile engine. It now produces NormalizedRace
    objects to be compatible with the V2Scorer.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    races = []

    meeting_containers = soup.select('[class*="meeting"], [class*="accordion__row"]')
    if not meeting_containers:
        meeting_containers = [soup]

    for container in meeting_containers:
        try:
            course_element = container.select_one(
                'h1, h2, [class*="courseName"], [class*="course-name"]'
            )
            course_name = (
                course_element.get_text(strip=True) if course_element else "Unknown Course"
            )
            track_key = canonical_track_key(course_name)

            race_elements = container.select(
                '[class*="race-item"], [class*="meetingItem"], li a[href*="racecards/"]'
            )

            for race_el in race_elements:
                time_el = race_el.select_one('[class*="raceTime"], [class*="time"]')
                if not time_el:
                    continue
                race_time = time_el.get_text(strip=True)

                runners_el = race_el.select_one('[class*="runners"], [class*="numberOfRunners"]')
                field_size = 0
                if runners_el:
                    runners_match = re.search(r"(\d+)", runners_el.get_text())
                    if runners_match:
                        field_size = int(runners_match.group(1))

                # For the mobile engine, we don't have detailed runner data,
                # but we need to create dummy runners for the scorer to work.
                runners = []
                if field_size > 0:
                    # Create dummy runners with plausible odds for scoring
                    runners.append(
                        NormalizedRunner(
                            runner_id="fav",
                            name="Simulated Fav",
                            saddle_cloth="1",
                            odds_decimal=2.0,
                        )
                    )
                    runners.append(
                        NormalizedRunner(
                            runner_id="2nd-fav",
                            name="Simulated 2nd Fav",
                            saddle_cloth="2",
                            odds_decimal=4.0,
                        )
                    )
                    for i in range(2, field_size):
                        runners.append(
                            NormalizedRunner(
                                runner_id=f"runner-{i + 1}",
                                name=f"Runner {i + 1}",
                                saddle_cloth=str(i + 1),
                                odds_decimal=10.0 + i,
                            )
                        )

                race = NormalizedRace(
                    race_key=canonical_race_key(track_key, race_time),
                    track_key=track_key,
                    start_time_iso=f"{date.today().isoformat()}T{parse_hhmm_any(race_time)}:00Z",
                    runners=runners,
                    source_ids=[source_name],
                )
                races.append(race)
        except Exception as e:
            logging.warning(f"Could not parse a container from {source_name}: {e}")
            continue

    return races


# =============================================================================
# --- MAIN MONITORING LOOP & ENTRY POINT ---
# =============================================================================


async def perform_scan_and_alert(config: Dict, scorer: V2Scorer, alerted_ids: Set[str]):
    """
    Performs a single, full cycle of fetching, parsing, scoring, and alerting
    using the V2 data models and the new resilient fetching logic.
    """
    logging.info("=" * 20 + " Starting New Scan Cycle " + "=" * 20)
    all_races: Dict[str, NormalizedRace] = {}

    # Create a list of fetch tasks
    fetch_tasks = [resilient_get(source["url"]) for source in config.get("SOFT_TARGET_SOURCES", [])]
    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    for i, res in enumerate(results):
        source_name = config["SOFT_TARGET_SOURCES"][i]["name"]
        if isinstance(res, Exception):
            logging.error(f"Failed to fetch {source_name}: {res}")
            continue

        html = res.text
        if not html:
            continue
        source_name = config["SOFT_TARGET_SOURCES"][i]["name"]
        parsed_races = parse_source(html, source_name)

        for race in parsed_races:
            if race.race_key not in all_races:
                all_races[race.race_key] = race
            elif len(race.runners) > len(all_races[race.race_key].runners):
                all_races[race.race_key] = race  # Keep the one with more runner info

    logging.info(f"Scan complete. Found {len(all_races)} unique races.")

    new_alerts = 0
    min_score_to_alert = config.get("ALERTS", {}).get("MINIMUM_SCORE_TO_ALERT", 85.0)

    for race in all_races.values():
        score_result = scorer.score_race(race)

        if score_result.score >= min_score_to_alert and race.race_key not in alerted_ids:
            title = f"[ALERT] Target Found! (Score: {score_result.score})"
            content = f"{race.start_time_iso[11:16]} {race.track_key.replace('_', ' ').title()} ({len(race.runners)} runners)"
            send_termux_notification(title, content)
            alerted_ids.add(race.race_key)
            new_alerts += 1

    if new_alerts > 0:
        logging.info(f"Found and sent {new_alerts} new alerts.")
        save_alert_state(Path(config["ALERTS"]["STATE_FILE"]), alerted_ids)
    else:
        logging.info("No new target opportunities found this cycle.")


def main():
    """
    Main function to initialize and run the continuous monitoring loop.
    """
    print("--- Mobile Engine Main Function Started ---")
    config = load_config()
    if not config:
        return

    setup_logging(config.get("LOG_FILE", "mobile_app.log"))
    logging.info(f"--- {config.get('APP_NAME', 'Mobile Alerter')} Starting Up ---")

    scorer = V2Scorer(config)
    state_file = Path(config.get("ALERTS", {}).get("STATE_FILE", "daily_alerts.json"))
    alerted_race_ids = load_alert_state(state_file)
    logging.info(f"Loaded {len(alerted_race_ids)} previously alerted races from state file.")

    # The spectral scheduler will run the perform_scan_and_alert function in bursts.
    # The lambda function is used to pass the arguments to perform_scan_and_alert.
    scan_function = lambda: perform_scan_and_alert(config, scorer, alerted_race_ids)

    try:
        safe_async_run(run_bursts(scan_function), "Mobile Alert Engine")
    except KeyboardInterrupt:
        logging.info("\nCtrl+C detected. Shutting down the engine.")
    except Exception as e:
        logging.critical(f"A critical error occurred in the main loop: {e}", exc_info=True)
    finally:
        save_alert_state(state_file, alerted_race_ids)
        logging.info("Final alert state saved.")
        sys.exit(0)


if __name__ == "__main__":
    main()
