import nest_asyncio
nest_asyncio.apply()
#!/usr/bin/env python3
"""
Paddock Parser Toolkit v2.0 - Main Entry Point

This script serves as the main entry point for the unified toolkit. It has
been refactored to provide a seamless, action-oriented user experience,
integrating the V2 adapter pipeline and the V1 local file parser.
"""

import sys
import logging
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
import time

# --- Module Imports ---
try:
    from config_manager import config_manager
    # V1 modules (still used for specific tasks)
    from enhanced_scanner import test_scanner_connections, run_batch_prefetch
    from paddock_parser import run_batch_parse, run_persistent_engine, parse_local_files, merge_normalized_races, generate_paddock_reports
    from link_helper import create_and_launch_link_helper

    # V2 modules
    import adapters # This triggers the loading of all adapters
    from analysis import run_v2_adapter_pipeline, score_races, display_results_console
    from normalizer import NormalizedRace

except ImportError as e:
    print(f"FATAL: Could not import required modules: {e}", file=sys.stderr)
    print("Ensure all required files are present.", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# --- SETUP & HELPERS ---
# =============================================================================

def setup_logging(log_file: str):
    """Configures logging for the application."""
    log_dir = Path(log_file).parent
    log_dir.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def safe_async_run(coro, operation_name: str = "Operation"):
    """Safely run async operations with unified error handling."""
    try:
        print(f"Starting {operation_name}...")
        return asyncio.run(coro)
    except KeyboardInterrupt:
        print(f"\n⚠️ {operation_name} cancelled by user.")
    except Exception as e:
        logging.error(f"{operation_name} failed: {e}", exc_info=True)
        print(f"❌ Error during {operation_name}: {e}")

# =============================================================================
# --- CORE UNIFIED PIPELINE (V3 COMPLIANT) ---
# =============================================================================

async def run_unified_pipeline(args: Optional[argparse.Namespace]):
    """
    The main, unified data processing pipeline. It now uses the global
    config_manager and does not need the config object passed around.
    """
    print("\n--- Starting Unified Analysis Pipeline ---")

    # 1. Get races from V2/V3 adapters
    print("==> Phase 1: Fetching data from live adapters...")
    races_from_adapters = await run_v2_adapter_pipeline()
    print(f"==> Found {len(races_from_adapters)} races from live adapters.")

    # The V1 local file parser still needs the config dict for now.
    config = config_manager.get_config()

    # 2. Get races from V1 local files
    print("\n==> Phase 2: Parsing local HTML files...")
    loop = asyncio.get_running_loop()
    races_from_local = await loop.run_in_executor(
        None, parse_local_files, config, args
    )
    print(f"==> Found {len(races_from_local)} races from local files.")

    # 3. Merge the two lists of races
    print("\n==> Phase 3: Merging data from all sources...")
    all_races_by_key: Dict[str, NormalizedRace] = {r.race_key: r for r in races_from_adapters}
    for local_race in races_from_local:
        if local_race.race_key in all_races_by_key:
            existing = all_races_by_key[local_race.race_key]
            all_races_by_key[local_race.race_key] = merge_normalized_races(existing, local_race)
        else:
            all_races_by_key[local_race.race_key] = local_race

    final_races = list(all_races_by_key.values())
    if not final_races:
        print("✅ Analysis complete. No races found from any source.")
        return

    print(f"Found {len(final_races)} unique races across all sources.")

    # 4. Score and generate reports (V3 compliant)
    print("Scoring races...")
    scored_results = score_races(final_races)

    # 5. Display and save reports
    display_results_console(scored_results)
    generate_paddock_reports(scored_results, config) # V1 report generator still needs config
    print("✅ Unified analysis pipeline complete.")

# =============================================================================
# --- INTERACTIVE MENU ---
# =============================================================================

def main_menu():
    """Displays the action-oriented main menu for the user."""
    config = config_manager.get_config()
    app_name = config.get('APP_NAME', 'Paddock Parser Toolkit')

    while True:
        print("\n" + "="*60)
        print(f" {app_name} v3.0 - Main Menu")
        print("="*60)
        print("--- Analysis ---")
        print(" 1. Run Full Analysis (Live Adapters + Local Files)")
        print(" 2. Parse Local Files Only")
        print(" 3. Launch Live Paste Engine")
        print()
        print("--- Data Collection & Tools ---")
        print(" 4. Pre-Fetch HTML Sources")
        print(" 5. Open Manual Collection Helper")
        print(" 6. Test All Source Connections")
        print(" 7. View & Validate Configuration")
        print()
        print(" Q. Quit")
        print("="*60)

        choice = input("Enter your choice: ").strip().upper()

        if choice == '1':
            safe_async_run(run_unified_pipeline(None), "Unified Analysis")
        elif choice == '2':
            run_batch_parse(config, None) # V1 module, still needs config
        elif choice == '3':
            run_persistent_engine(config, argparse.Namespace()) # V1 module
        elif choice == '4':
            safe_async_run(run_batch_prefetch(config), "Pre-Fetch") # V1 module
        elif choice == '5':
            create_and_launch_link_helper(config) # V1 module
        elif choice == '6':
            safe_async_run(test_scanner_connections(config), "Connection Test") # V1 module
        elif choice == '7':
            print("\n--- Current Configuration (via ConfigManager) ---")
            for key, value in config.items():
                if isinstance(value, list):
                    print(f"- {key}: {len(value)} items")
                elif isinstance(value, dict):
                     print(f"- {key}: {len(value.keys())} keys")
                else:
                    print(f"- {key}: {value}")
            print("---------------------------")
        elif choice == 'Q':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice, please try again.")

        if choice != 'Q':
            input("\nPress Enter to return to the menu...")

# =============================================================================
# --- COMMAND-LINE INTERFACE ---
# =============================================================================

def main_cli(args: argparse.Namespace):
    """Handles command-line argument parsing and execution."""
    config = config_manager.get_config()
    if args.command == 'analyze':
        safe_async_run(run_unified_pipeline(args), "Unified Analysis")
    elif args.command == 'parse':
        run_batch_parse(config, args) # V1 module
    elif args.command == 'persistent':
        run_persistent_engine(config, args) # V1 module
    elif args.command == 'collect':
        create_and_launch_link_helper(config) # V1 module
    elif args.command == 'prefetch':
        safe_async_run(run_batch_prefetch(config), "Pre-Fetch") # V1 module
    elif args.command == 'test':
        safe_async_run(test_scanner_connections(config), "Connection Test") # V1 module
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

def create_cli_parser() -> argparse.ArgumentParser:
    """Create and configure the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Paddock Parser Toolkit v2.0 - A Unified Racing Intelligence Tool",
        epilog="Use '<command> --help' for command-specific options."
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    # Unified 'analyze' command
    analyze_parser = subparsers.add_parser('analyze', help="Run the full unified analysis (live adapters + local files)")
    analyze_parser.add_argument('--input-dir', help="Local HTML directory (overrides config)")
    analyze_parser.add_argument('--date', help="Date to scan in YYYY-MM-DD format", default=None)

    # Standalone 'parse' command for local files only
    parse_parser = subparsers.add_parser('parse', help="Parse local HTML files only")
    parse_parser.add_argument('--input-dir', help="Input directory path (overrides config)")

    # Persistent engine command
    persistent_parser = subparsers.add_parser('persistent', help="Launch the 'Always-On' live paste engine")
    persistent_parser.add_argument('--cache-dir', help="Directory for cache files (overrides config)")
    persistent_parser.add_argument('--disable-cache-backup', action='store_true', help="Disable cache backup")
    persistent_parser.add_argument('--paste-sentinel', default='KABOOM', help="Sentinel string")

    # Data collection commands
    subparsers.add_parser('collect', help="Generate the manual collection helper page")
    prefetch_parser = subparsers.add_parser('prefetch', help="Pre-fetch all accessible HTML data sources")
    prefetch_parser.add_argument('--date', help="Date to fetch in YYYY-MM-DD format", default=None)
    subparsers.add_parser('test', help="Test all data source connections")

    return parser

# =============================================================================
# --- MAIN EXECUTION ---
# =============================================================================

if __name__ == "__main__":
    try:
        # V3: The config_manager is now the single source of truth.
        # We get the config from it only when needed for logging or legacy modules.
        config = config_manager.get_config()
        setup_logging(config.get("LOG_FILE", "app.log"))
        logging.info(f"Starting {config.get('APP_NAME', 'Paddock Parser Toolkit')} v3.0")

        if len(sys.argv) > 1:
            parser = create_cli_parser()
            args = parser.parse_args()
            main_cli(args)
        else:
            main_menu()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logging.critical(f"A fatal error occurred: {e}", exc_info=True)
        print(f"\n❌ A fatal error occurred: {e}")
        sys.exit(1)
