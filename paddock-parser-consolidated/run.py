#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Main Execution Entry Point
"""

import sys
import logging
from paddock_parser.main import main_cli, main_menu, create_cli_parser, setup_logging
from paddock_parser.config_manager import config_manager


if __name__ == "__main__":
    # V3: The config_manager is now the single source of truth.
    # We get the config from it only when needed for logging or legacy modules.
    config = config_manager.get_config()
    setup_logging(config.get("LOG_FILE", "app.log"))
    logging.info(f"Starting {config.get('APP_NAME', 'Paddock Parser Toolkit')} v3.0 from run.py")

    # To run with command-line arguments, provide them as usual.
    # e.g., python run.py analyze
    # To run the interactive menu, run with no arguments.
    # e.g., python run.py
    if len(sys.argv) > 1:
        parser = create_cli_parser()
        args = parser.parse_args()
        main_cli(args)
    else:
        main_menu()
