#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Main Execution Entry Point
"""
import sys
from paddock_parser.main import main_cli, main_menu

if __name__ == "__main__":
    # To run with command-line arguments, provide them as usual.
    # e.g., python run.py analyze
    # To run the interactive menu, run with no arguments.
    # e.g., python run.py
    if len(sys.argv) > 1:
        main_cli()
    else:
        main_menu()
