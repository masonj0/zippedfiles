import asyncio
from main import advanced_prefetch_once, setup_logging
from config import load_config
import logging

async def main():
    # Setup logging to see the output
    config = load_config()
    if not config:
        print("Failed to load config")
        return
    setup_logging(config.get("LOG_FILE", "app.log"))
    logging.info("--- Running Advanced Prefetch Test ---")
    await advanced_prefetch_once()
    logging.info("--- Advanced Prefetch Test Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
