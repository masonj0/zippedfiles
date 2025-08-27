import httpx
import logging

async def simple_get(url: str):
    """
    A very simple, stripped-down async get function.
    """
    try:
        async with httpx.AsyncClient() as client:
            logging.info(f"[simple_get] Fetching {url}")
            # Set a generous timeout
            response = await client.get(url, timeout=30.0)
            logging.info(f"[simple_get] Got response with status {response.status_code}")
            response.raise_for_status()
            return response
    except httpx.HTTPError as e:
        logging.error(f"[simple_get] HTTP error fetching {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"[simple_get] General error fetching {url}: {e}", exc_info=True)
        return None
