import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigurationManager:
    """
    A centralized manager for loading and accessing application configuration.
    This class is the single source of truth for all settings, preventing
    conflicts and ensuring consistent behavior.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config_settings.json"):
        # The __init__ will only run on the first instantiation
        if hasattr(self, "_config"):
            return

        self.config_path = Path(config_path)
        self._config = self._load_config()
        logging.info(f"ConfigurationManager initialized with config from '{self.config_path}'.")

    def _load_config(self) -> Dict[str, Any]:
        """
        Loads the main configuration file from the specified path.
        """
        if not self.config_path.exists():
            logging.critical(f"FATAL: Configuration file '{self.config_path}' not found.")
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.critical(
                f"FATAL: Could not parse configuration file '{self.config_path}': {e}."
            )
            return {}

    def get_config(self) -> Dict[str, Any]:
        """
        Returns the entire loaded configuration dictionary.
        """
        return self._config

    def get_adapter_config(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Intelligently retrieves the configuration for a specific adapter source_id.

        It provides backward compatibility by searching in this order:
        1. The new `DATA_SOURCES_V2` dictionary (preferred).
        2. The legacy `DATA_SOURCES` list of lists.

        Returns the site-specific config dictionary if found and enabled, otherwise None.
        """
        if not source_id:
            return None

        # 1. Search in the new V2 dictionary format
        data_sources_v2 = self._config.get("DATA_SOURCES_V2", {})
        if source_id in data_sources_v2:
            site_config = data_sources_v2[source_id]
            if site_config.get("enabled", False):
                logging.debug(f"Found V2 config for '{source_id}'.")
                return site_config

        # 2. Search in the legacy V1 list format for backward compatibility
        legacy_sources = self._config.get("DATA_SOURCES", [])
        for category in legacy_sources:
            for site in category.get("sites", []):
                # Check if the canonical name matches the source_id
                # This requires a helper to create canonical names, but for now we'll do a simple check
                if source_id.lower() in site.get("name", "").lower():
                    if site.get("enabled", False):
                        logging.debug(
                            f"Found legacy config for '{source_id}' in '{site.get('name')}'."
                        )
                        return site

        logging.info(f"No enabled configuration found for adapter '{source_id}'.")
        return None


# Global instance for easy access across the application
config_manager = ConfigurationManager()
