#!/usr/bin/env python3
"""
Paddock Parser Toolkit - The Core Parser (V1 Refactored)
"""

import logging
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag

from paddock_parser.normalizer import (
    normalize_course_name,
    parse_hhmm_any,
    convert_odds_to_fractional_decimal,
    map_discipline,
)

class RacingDataParser:
    """
    A robust parser for extracting racing data from various HTML structures.
    """

    def __init__(self):
        self.SELECTORS = {
            "race_block": [".race-card", ".race-card-wrapper", "div.rac-card", ".card.race"],
            "course_name": ["h1", "h2.title", ".course-name", "a.breadcrumb-item"],
            "race_time": [".race-time", "span.time", "div.r-card-time"],
            "race_type": [".race-title", ".race-header .title", "span.race-name"],
            "runner_row": ["tr.runner-row", "div.runner-item", ".runner-info-row"],
            "runner_name": [".runner-name", "a.runner-link", "span.horse-name"],
            "runner_number": [".saddle-cloth", "span.number", "td.runner-no"],
            "runner_odds": [".odds", "span.price", "td.odds-cell"],
        }
        logging.info("RacingDataParser initialized with V1 selector maps.")

    def _find_first_text(self, element: Tag, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            found = element.select_one(selector)
            if found and found.get_text(strip=True):
                return found.get_text(strip=True)
        return None

    def _parse_single_race(self, race_block: Tag, source_file: str) -> Optional[Dict[str, Any]]:
        try:
            course = self._find_first_text(race_block, self.SELECTORS["course_name"])
            time = self._find_first_text(race_block, self.SELECTORS["race_time"])
            race_type = self._find_first_text(race_block, self.SELECTORS["race_type"])

            if not all([course, time]):
                return None

            normalized_course = normalize_course_name(course)
            normalized_time = parse_hhmm_any(time)
            discipline = map_discipline(race_type or "")

            runners = []
            for runner_row in race_block.select(','.join(self.SELECTORS["runner_row"])):
                runner_name = self._find_first_text(runner_row, self.SELECTORS["runner_name"])
                runner_no = self._find_first_text(runner_row, self.SELECTORS["runner_number"])
                runner_odds = self._find_first_text(runner_row, self.SELECTORS["runner_odds"])

                if runner_name:
                    runners.append({
                        "name": runner_name,
                        "number": runner_no,
                        "odds_str": runner_odds,
                        "odds_decimal": convert_odds_to_fractional_decimal(runner_odds),
                    })

            if not runners:
                return None

            return {
                "id": f"{normalized_course}_{normalized_time}".replace(":", ""),
                "course": normalized_course,
                "race_time": normalized_time,
                "race_type": race_type,
                "discipline": discipline,
                "runners": runners,
                "source_file": source_file,
                "utc_datetime": self._get_utc_datetime(normalized_time),
            }
        except Exception as e:
            logging.error(f"Error parsing a race block: {e}", exc_info=True)
            return None

    def _get_utc_datetime(self, race_time_str: Optional[str]) -> Optional[str]:
        if not race_time_str:
            return None
        try:
            today = date.today()
            hour, minute = map(int, race_time_str.split(':'))
            local_dt = datetime(today.year, today.month, today.day, hour, minute)
            return local_dt.isoformat() + "Z"
        except (ValueError, TypeError):
            return None

    def parse_racing_data(self, html_content: str, source_file: str) -> List[Dict[str, Any]]:
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')

        race_blocks = soup.select(','.join(self.SELECTORS["race_block"]))

        if not race_blocks:
            logging.warning(f"No race blocks found in '{source_file}' using V1 selectors.")
            return []

        logging.info(f"Found {len(race_blocks)} potential race blocks in '{source_file}'.")

        parsed_races = []
        for block in race_blocks:
            parsed_race = self._parse_single_race(block, source_file)
            if parsed_race:
                parsed_races.append(parsed_race)

        logging.info(f"Successfully parsed {len(parsed_races)} races from '{source_file}'.")
        return parsed_races

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parser = RacingDataParser()
        races = parser.parse_racing_data(content, file_path)
        import json
        print(json.dumps(races, indent=2))
    else:
        print("Usage: python racing_data_parser.py <path_to_html_file>")
