import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from ..config_manager import ConfigurationManager
from ..sources import RawRaceDocument


class BaseAdapterV3(ABC):
    """
    The V3 abstract base class for all data source adapters.

    This architecture enforces a two-step initialization process:
    1. __init__: The adapter is created but not yet configured. It receives a
       reference to the global ConfigurationManager.
    2. initialize(): The adapter uses the ConfigurationManager to fetch its
       specific settings. This method must return True on success.

    This ensures no adapter can be run in a partially-configured or
    un-configured state, improving overall system stability.
    """

    source_id: str = "base_adapter_v3"

    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager
        self.site_config: Optional[Dict[str, Any]] = None
        self.is_initialized: bool = False

    def initialize(self) -> bool:
        """
        Loads the adapter's specific configuration using the ConfigurationManager.
        Returns True if configuration is found and the adapter is enabled,
        otherwise False.
        """
        self.site_config = self.config_manager.get_adapter_config(self.source_id)
        if self.site_config:
            self.is_initialized = True
            logging.info(f"V3 Adapter '{self.source_id}' initialized successfully.")
            return True

        logging.info(
            f"V3 Adapter '{self.source_id}' could not be initialized (config not found or disabled)."
        )
        self.is_initialized = False
        return False

    @abstractmethod
    async def fetch(self) -> List[RawRaceDocument]:
        """
        The core method for fetching data from the source.
        This must be implemented by all concrete adapter classes.
        """
        raise NotImplementedError(
            "The 'fetch' method must be implemented by a subclass of BaseAdapterV3."
        )
