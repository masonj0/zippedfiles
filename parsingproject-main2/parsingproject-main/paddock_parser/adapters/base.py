import logging
from urllib.parse import urlparse
from ..sources import RawRaceDocument

class BaseV2Adapter:
    """A base class for V2 adapters to share common logic."""
    source_id: str = "base_adapter"

    def __init__(self, config: dict):
        self.config = config
        self.site_config = self._find_site_config(config)

    def _find_site_config(self, config: dict) -> dict | None:
        """
        Finds the specific configuration for this adapter by reading the
        new DATA_SOURCES_V2 dictionary.
        """
        data_sources_v2 = config.get("DATA_SOURCES_V2", {})

        # The source_id of the adapter class must match a key in the config
        site_config = data_sources_v2.get(self.source_id)

        if not site_config or not site_config.get("enabled", False):
            logging.info(f"Configuration for source_id '{self.source_id}' not found or not enabled in config.json.")
            return None

        # Add the base_url to the config for convenience, if not already present
        if 'base_url' not in site_config and 'url' in site_config:
            parsed_url = urlparse(site_config['url'])
            site_config['base_url'] = f"{parsed_url.scheme}://{parsed_url.netloc}"

        logging.info(f"Found and enabled configuration for source_id: '{self.source_id}'")
        return site_config

    async def fetch(self) -> list[RawRaceDocument]:
        """Each adapter must implement its own fetch method."""
        raise NotImplementedError(f"Fetch method not implemented for adapter: {self.__class__.__name__}")
