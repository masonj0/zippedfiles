#!/usr/bin/env python3
import json
import logging
import sys
from typing import Dict, Any

def load_config(path: str = 'config_settings.json') -> Dict[str, Any]:
    """
    Loads the main configuration file.
    On critical errors (file not found, parse error), it logs the error
    and exits the application to prevent running in a broken state.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file '{path}' not found. Using empty config and default values.")
        return {}
    except json.JSONDecodeError as e:
        logging.critical(f"FATAL: Could not parse configuration file '{path}': {e}. Application cannot continue.")
        sys.exit(1)
    return {}

# =============================================================================
# --- GLOBAL CONFIG CONSTANTS ---
# Load the config at module level to expose keys as importable constants.
# =============================================================================
_config = load_config()

# Expose top-level keys as module-level constants for easy import
SCHEMA_VERSION = _config.get("SCHEMA_VERSION", "1.0")
APP_NAME = _config.get("APP_NAME", "Paddock Parser Toolkit")
INPUT_DIR = _config.get("INPUT_DIR", "html_input")
DEFAULT_OUTPUT_DIR = _config.get("DEFAULT_OUTPUT_DIR", "output")
LOG_FILE = _config.get("LOG_FILE", "app.log")

# Scraping-specific constants
HTTP_CLIENT = _config.get("HTTP_CLIENT", {})
HTTP_HEADERS = _config.get("HTTP_HEADERS", {})
SCRAPER = _config.get("SCRAPER", {})
FINGERPRINTS = _config.get("FINGERPRINTS", [])
STEALTH_HEADERS = _config.get("STEALTH_HEADERS", {})
CACHE_BUST_HEADERS = _config.get("CACHE_BUST_HEADERS", {})
UA_FAMILIES = _config.get("UA_FAMILIES", {})
BIZ_HOURS = _config.get("BIZ_HOURS", {"start_local": 0, "end_local": 24})

# Data source configurations
DATA_SOURCES_V2 = _config.get("DATA_SOURCES_V2", {})
LEGACY_DATA_SOURCES = _config.get("LEGACY_DATA_SOURCES", [])

# Other settings
TIMEZONES = _config.get("TIMEZONES", {})
SCORER_WEIGHTS = _config.get("SCORER_WEIGHTS", {})
PROXY_VIEWERS = _config.get("PROXY_VIEWERS", [])
TEMPLATE_PADDOCK = _config.get("TEMPLATE_PADDOCK", "template_paddock.html")

# Add a check to ensure FINGERPRINTS has at least one entry to avoid errors
if not FINGERPRINTS:
    FINGERPRINTS.append({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    logging.warning("No FINGERPRINTS found in config, using a single default fingerprint.")
