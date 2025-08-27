#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Portable "Elevator Pitch" Demo
... (docstring) ...
"""
import asyncio
import logging
import sys
import os
import json
from pathlib import Path

# Get project root and change CWD *before* importing the package.
project_root = Path(__file__).resolve().parent
# Note: In a real-world scenario, you wouldn't change the CWD.
# This is done here to ensure the package can be found in this specific
# portable demo setup. A better approach for a real client application
# would be to install the paddock_parser package properly.
os.chdir(project_root)

# Now that the CWD is the project root, we can safely import our package.
try:
    from paddock_parser.main import run_unified_pipeline, setup_logging
    from paddock_parser.config_manager import config_manager
    from paddock_parser.fetching import breadcrumb_get, close_shared_async_client
except ImportError as e:
    print("FATAL: Could not import the paddock_parser package.", file=sys.stderr)
    print("Please ensure you have installed the project in editable mode (`pip install -e .`) from the project root.", file=sys.stderr)
    print(f"Original error: {e}", file=sys.stderr)
    sys.exit(1)

def force_reload_config():
    """
    A robust way to ensure the config_manager singleton is correctly loaded,
    bypassing any potential CWD or import order issues.
    """
    config_file_path = project_root / "config_settings.json"
    if not config_file_path.exists():
        logging.error(f"FATAL: `config_settings.json` not found at {config_file_path}")
        sys.exit(1)

    try:
        with open(config_file_path, 'r') as f:
            correct_config = json.load(f)
        # Forcefully reset the singleton's internal config dictionary
        config_manager._config = correct_config
        logging.info(f"Successfully force-reloaded configuration from {config_file_path}")
    except Exception as e:
        logging.error(f"FATAL: Failed to load or parse config file at {config_file_path}: {e}")
        sys.exit(1)


def demonstrate_race_filtering():
    """
    A demonstration of how to programmatically set configuration to
    filter for specific races before running the pipeline.
    """
    print("\n--- DEMO: Configuring Race Filters ---")
    config = config_manager.get_config()
    race_filters = {"MIN_RUNNERS": 4, "MAX_RUNNERS": 6}
    config["RACE_FILTERS"] = race_filters
    print(f"Configuration updated to filter for races with {race_filters['MIN_RUNNERS']}-{race_filters['MAX_RUNNERS']} runners.")
    print("-" * 35)

async def demonstrate_breadcrumb_fetching():
    """
    A demonstration of the 'breadcrumb' fetching technique to mimic human
    navigation and bypass simple anti-scraping measures.
    """
    print("\n--- DEMO: Improved Fetching with Breadcrumbs ---")
    print("This technique mimics a user clicking through a site, which can bypass some anti-bot measures.")

    urls_to_visit = [
        "https://www.timeform.com/horse-racing",
        "https://www.timeform.com/horse-racing/racecards"
    ]

    print(f"Attempting to fetch the final page by visiting: {urls_to_visit}")

    try:
        response = await breadcrumb_get(urls_to_visit)
        print(f"Successfully fetched final page: {response.url}")
        print(f"Response status: {response.status_code}")
        # We won't print the content to keep the demo clean.
    except Exception as e:
        print(f"ERROR: Breadcrumb fetch failed: {e}")
    finally:
        # It's important to close the shared client when we're done.
        await close_shared_async_client()

    print("-" * 45)


async def main():
    """
    Main function to run the portable demo.
    """
    print("\n--- Paddock Parser Toolkit: Portable Demo ---")

    # Force-reload the configuration to be absolutely sure it's correct.
    force_reload_config()

    config = config_manager.get_config()
    setup_logging(config.get("LOG_FILE", "app.log"))

    # Demonstrate improved fetching
    await demonstrate_breadcrumb_fetching()

    # Demonstrate programmatic configuration
    demonstrate_race_filtering()

    # Run the main analysis pipeline
    # Note: The pipeline will use its own fetching logic internally.
    # The breadcrumb demo above is just to showcase the capability.
    await run_unified_pipeline(config=config, args=None)

    print("\n--- Demo Complete ---")


if __name__ == "__main__":
    try:
        # In this updated version, we have multiple async calls in main,
        # so we make main async and run it with asyncio.run().
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo cancelled by user.")
    except Exception as e:
        logging.critical("An unexpected error occurred during the demo.", exc_info=True)
        print(f"FATAL ERROR: {e}")
