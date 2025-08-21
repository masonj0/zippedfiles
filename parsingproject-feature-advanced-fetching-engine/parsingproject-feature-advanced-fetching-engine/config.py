#!/usr/bin/env python3
import json
import logging
import sys
from pathlib import Path
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
SCHEMA_VERSION = _config.get("SCHEMA_VERSION", "2.0")
APP_NAME = _config.get("APP_NAME", "Paddock Parser Toolkit")
INPUT_DIR = _config.get("INPUT_DIR", "html_input")
DEFAULT_OUTPUT_DIR = _config.get("DEFAULT_OUTPUT_DIR", "output")
LOG_FILE = _config.get("LOG_FILE", "app.log")
TEMPLATE_PADDOCK = _config.get("TEMPLATE_PADDOCK", "template_paddock.html")
TEMPLATE_SCANNER = _config.get("TEMPLATE_SCANNER", "template_scanner.html")


# Expose nested dictionaries as constants.
# Use .get(key, {}) to ensure they are always dicts, preventing KeyErrors.
HTTP = _config.get("HTTP", {})
ScraperFeatures = _config.get("ScraperFeatures", {})
Proxies = _config.get("Proxies", {})
Fingerprints = _config.get("Fingerprints", [])
StealthHeaders = _config.get("StealthHeaders", {})
CacheBustHeaders = _config.get("CacheBustHeaders", {})
SpectralScheduler = _config.get("SpectralScheduler", {})
Webhook = _config.get("Webhook", {})
DNSResolvers = _config.get("DNSResolvers", [])
DATA_SOURCES_V2 = _config.get("DATA_SOURCES_V2", {})
LEGACY_DATA_SOURCES = _config.get("LEGACY_DATA_SOURCES", [])
SCORER_WEIGHTS = _config.get("SCORER_WEIGHTS", {})


# Add a check to ensure Fingerprints has at least one entry to avoid errors
if not Fingerprints:
    Fingerprints.append({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    logging.warning("No Fingerprints found in config, using a single default fingerprint.")
