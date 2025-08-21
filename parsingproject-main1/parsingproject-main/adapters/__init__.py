import pkgutil
import importlib
import logging

# This will hold the registered adapters, which are stored in the sources module
from sources import ADAPTERS

def load_all_adapters():
    """
    Dynamically imports all modules in the 'adapters' package to ensure
    that the @register_adapter decorator is called for all defined adapters.
    """
    # We only need to run this once. If ADAPTERS is already populated, we can skip.
    # This check assumes that this init file is the only place adapters are loaded from.
    # If other code could add adapters, this logic might need adjustment.
    if not ADAPTERS:
        logging.info("Loading all source adapters from 'adapters' package...")
        for _, name, _ in pkgutil.iter_modules(__path__):
            try:
                importlib.import_module(f".{name}", __name__)
                logging.debug(f"Successfully loaded adapter module: {name}")
            except Exception as e:
                logging.error(f"Failed to load adapter module {name}: {e}", exc_info=True)
        logging.info(f"Finished loading adapters. Found {len(ADAPTERS)} registered adapters.")

# Call the function to load adapters when this package is imported.
# This makes the adapters available in the global ADAPTERS list defined in sources.py
load_all_adapters()
