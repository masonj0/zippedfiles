import logging
from typing import Protocol, List, Dict, Any, Type
from dataclasses import dataclass, field

# A global registry for all adapters
ADAPTERS: List[Type["SourceAdapter"]] = []

@dataclass
class FieldConfidence:
    """Holds a value and our confidence in its accuracy."""
    value: Any
    confidence: float  # 0.0 to 1.0
    source: str

@dataclass
class RunnerDoc:
    """A document representing a single runner in a race."""
    runner_id: str
    name: FieldConfidence
    number: FieldConfidence
    odds: FieldConfidence | None = None
    jockey: FieldConfidence | None = None
    trainer: FieldConfidence | None = None
    extras: Dict[str, FieldConfidence] = field(default_factory=dict)

@dataclass
class RawRaceDocument:
    """
    A raw, unprocessed document for a single race from a specific source.
    This is the data structure that adapters are expected to return.
    """
    source_id: str
    fetched_at: str  # ISO 8601 timestamp
    track_key: str   # e.g., "ascot"
    race_key: str    # e.g., "ascot_1430"
    start_time_iso: str
    runners: List[RunnerDoc]
    extras: Dict[str, FieldConfidence] = field(default_factory=dict)

class SourceAdapter(Protocol):
    """
    The protocol that all data source adapters must conform to.
    Adapters are responsible for fetching and parsing data from a single
    source (e.g., Timeform, Racing Post) and returning it in a standardized
    RawRaceDocument format.
    """
    source_id: str

    def __init__(self, config: Dict[str, Any]):
        ...

    async def fetch(self) -> List[RawRaceDocument]:
        """
        Fetches data from the source and returns a list of raw race documents.
        """
        ...

def register_adapter(cls: Type[SourceAdapter]) -> Type[SourceAdapter]:
    """
    A class decorator to register a new adapter in the global registry.
    """
    if not hasattr(cls, "source_id"):
        raise TypeError(f"Adapter {cls.__name__} must have a 'source_id' attribute.")

    if cls not in ADAPTERS:
        logging.info(f"Registering adapter: {cls.__name__} for source '{cls.source_id}'")
        ADAPTERS.append(cls)
    return cls
