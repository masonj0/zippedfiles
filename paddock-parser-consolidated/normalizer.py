#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Shared Normalizer Module (V2)
# normalizer.py

This module is the single source of truth for all data cleaning, normalization,
and key generation logic. It ensures data consistency across the entire toolkit.
V2 introduces versioned, structured dataclasses for raw and normalized data.
"""

import re
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from sources import RawRaceDocument, RunnerDoc, FieldConfidence
import hashlib

# --- V2 DATA STRUCTURES ---

@dataclass
class NormalizedRunner:
    """
    A runner with all key fields normalized for consistent analysis.
    V2 of the data structure.
    """
    runner_id: str
    name: str
    saddle_cloth: str
    odds_decimal: float | None = None
    odds_fractional: str | None = None
    jockey_name: str | None = None
    trainer_name: str | None = None
    # Confidence scores for key fields
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    # Raw source-specific data for debugging and future use
    raw_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NormalizedRace:
    """
    A race with all key fields normalized.
    This is the primary data structure for the V2 analysis engine.
    V2 of the data structure.
    """
    race_key: str  # Globally unique key, e.g., "ascot_2025-08-18_1430"
    track_key: str
    start_time_iso: str
    race_name: str | None = None
    going: str | None = None
    runners: List[NormalizedRunner] = field(default_factory=list)
    # Metadata from various sources
    source_ids: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

# --- KEY GENERATION ---

def canonical_track_key(name: str) -> str:
    """Generates a standardized, URL-safe key for a racetrack."""
    if not name:
        return "unknown_track"
    # Lowercase, remove special chars, replace spaces with underscores
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s-]', '', name)
    name = re.sub(r'[\s-]+', '_', name)
    return name

def canonical_race_key(track_key: str, race_time: str) -> str:
    """Generates a globally unique key for a race."""
    # Assumes race_time is already in HHMM format
    time_str = re.sub(r'[^0-9]', '', race_time)
    return f"{track_key}::r{time_str}"

# --- NORMALIZATION FUNCTIONS ---

_COURSE_NAME_AT_REGEX = re.compile(r' at .*$')
_COURSE_NAME_PAREN_REGEX = re.compile(r'\s*\([^)]*\)')

def normalize_course_name(name: str) -> str:
    """Cleans and standardizes a racetrack name."""
    if not name:
        return ""
    name = name.lower().strip()
    name = _COURSE_NAME_AT_REGEX.sub('', name)
    name = _COURSE_NAME_PAREN_REGEX.sub('', name)
    replacements = {
        'park': '', 'raceway': '', 'racecourse': '', 'track': '',
        'stadium': '', 'greyhound': '', 'harness': ''
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return " ".join(name.split())

def map_discipline(discipline_name: str) -> str:
    """Maps a raw discipline string to a standardized category."""
    if not discipline_name:
        return "thoroughbred"
    d_lower = discipline_name.lower()
    if "greyhound" in d_lower or "dog" in d_lower:
        return "greyhound"
    if "harness" in d_lower or "trot" in d_lower or "standardbred" in d_lower:
        return "harness"
    if "jump" in d_lower or "chase" in d_lower or "hurdle" in d_lower or "national hunt" in d_lower:
        return "jump"
    return "thoroughbred"

def parse_hhmm_any(time_text: str) -> Optional[str]:
    """Parses a time string into a standardized 24-hour 'HH:MM' format."""
    if not time_text:
        return None
    match = re.search(r'(\d{1,2})[:.](\d{2})', str(time_text))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if 'pm' in str(time_text).lower() and hour != 12:
        hour += 12
    if 'am' in str(time_text).lower() and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"

def convert_odds_to_decimal(odds_str: str) -> float | None:
    """Converts various odds formats to a decimal float."""
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
        dec = float(s)
        return dec if dec > 1.0 else None
    except ValueError:
        return None

def convert_odds_to_fractional_decimal(odds_str: str) -> Optional[float]:
    """Legacy function for V1 compatibility. Returns None for invalid odds."""
    dec = convert_odds_to_decimal(odds_str)
    return (dec - 1.0) if dec is not None else None

def normalize_race_docs(doc: RawRaceDocument) -> NormalizedRace:
    """
    Transforms a RawRaceDocument from a source adapter into a clean,
    standardized NormalizedRace object ready for the analysis engine.
    """
    runners = []
    for r in doc.runners:
        odds_decimal = convert_odds_to_decimal(r.odds.value if r.odds else None)

        confidence_scores = {
            "name": r.name.confidence,
            "odds": r.odds.confidence if r.odds else 0.0,
            "jockey": r.jockey.confidence if r.jockey else 0.0,
            "trainer": r.trainer.confidence if r.trainer else 0.0,
        }

        raw_data = {
            "extras": {k: v.value for k, v in r.extras.items()}
        }

        runners.append(NormalizedRunner(
            runner_id=r.runner_id,
            name=r.name.value,
            saddle_cloth=r.number.value,
            odds_decimal=odds_decimal,
            odds_fractional=r.odds.value if r.odds else None,
            jockey_name=r.jockey.value if r.jockey else None,
            trainer_name=r.trainer.value if r.trainer else None,
            confidence_scores=confidence_scores,
            raw_data=raw_data,
        ))

    return NormalizedRace(
        race_key=doc.race_key,
        track_key=doc.track_key,
        start_time_iso=doc.start_time_iso,
        runners=runners,
        source_ids=[doc.source_id],
        extras={k: v.value for k,v in doc.extras.items()}
    )
