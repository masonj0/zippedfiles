import logging
from adapters.base import BaseV2Adapter
from sources import RawRaceDocument, register_adapter

@register_adapter
class RacingPostAdapter(BaseV2Adapter):
    """
    Adapter for fetching racecards from Racing Post.
    NOTE: This adapter is a placeholder and is not yet implemented.
    """
    source_id = "racingpost"

    async def fetch(self) -> list[RawRaceDocument]:
        logging.warning(f"[{self.source_id}] The adapter for Racing Post is not yet implemented. Skipping fetch.")
        return []
