import logging
from .base import BaseV2Adapter
from ..sources import RawRaceDocument, register_adapter

@register_adapter
class AtTheRacesAdapter(BaseV2Adapter):
    """
    Adapter for fetching racecards from At The Races.
    NOTE: This adapter is a placeholder and is not yet implemented.
    """
    source_id = "attheraces"

    async def fetch(self) -> list[RawRaceDocument]:
        logging.warning(f"[{self.source_id}] The adapter for At The Races is not yet implemented. Skipping fetch.")
        return []
