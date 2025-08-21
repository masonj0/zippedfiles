from abc import ABC, abstractmethod
import logging
from typing import List
from normalizer import NormalizedRace

class BaseAdapterV3(ABC):
    """
    Abstract base class for all V3 data source adapters.
    """

    def __init__(self, name: str, enabled: bool, priority: int):
        self._name = name
        self._enabled = enabled
        self._priority = priority
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_name(self) -> str:
        return self._name

    def is_enabled(self) -> bool:
        return self._enabled

    def get_priority(self) -> int:
        return self._priority

    @abstractmethod
    def fetch_and_normalize(self) -> List[NormalizedRace]:
        """
        The core method for a V3 adapter.
        """
        pass

    @classmethod
    @abstractmethod
    def create_from_config(cls, config: dict) -> 'BaseAdapterV3':
        """
        A factory method to create an instance of the adapter from a config.
        """
        pass
