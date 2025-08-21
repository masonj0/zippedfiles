import logging
from adapters.base import BaseV2Adapter
from sources import RawRaceDocument, register_adapter

@register_adapter
class EquibaseAdapter(BaseV2Adapter):
    """
    Adapter for fetching racecards from Equibase.
    NOTE: This adapter is a placeholder and is not yet implemented.
    """
    source_id = "equibase"

    async def fetch(self) -> list[RawRaceDocument]:
        logging.warning(f"[{self.source_id}] The adapter for Equibase is not yet implemented. Skipping fetch.")
        return []
