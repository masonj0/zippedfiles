import nest_asyncio
nest_asyncio.apply()
#!/usr/bin/env python3
"""
Paddock Parser Toolkit v3.0 - Main Entry Point
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
    from enhanced_scanner import test_scanner_connections, run_batch_prefetch
    from paddock_parser import run_batch_parse, run_persistent_engine, parse_local_files, merge_normalized_races, generate_paddock_reports
    from link_helper import create_and_launch_link_helper
    from analysis import run_v3_analysis_pipeline, display_results_console
    from normalizer import NormalizedRace

except ImportError as e:
    print(f"FATAL: Could not import required modules: {e}", file=sys.stderr)
    print("Ensure all required files are present in the root directory.", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# --- SETUP & HELPERS ---
# =============================================================================

def setup_logging(log_file: str):
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
    try:
        print(f"Starting {operation_name}...")
        return asyncio.run(coro)
    except KeyboardInterrupt:
        print(f"\n⚠️ {operation_name} cancelled by user.")
    except Exception as e:
        logging.error(f"{operation_name} failed: {e}", exc_info=True)
        print(f"❌ Error during {operation_name}: {e}")

# =============================================================================
# --- CORE PIPELINE ---
# =============================================================================

async def run_unified_pipeline(args: Optional[argparse.Namespace]):
    """
    This pipeline is temporarily modified to ONLY run the V3 analysis for verification.
    """
    print("\n--- Starting V3 Analysis Pipeline Verification ---")

    scored_results = await run_v3_analysis_pipeline()

    if scored_results:
        print("\n✅ V3 pipeline executed and returned results.")
    else:
        print("\n⚠️ V3 pipeline ran but returned no results. Check logs for details.")

    print("--- V3 Analysis Pipeline Verification Complete ---")

# =============================================================================
# --- INTERACTIVE MENU ---
# =============================================================================

def main_menu():
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
            run_batch_parse(config, None)
        elif choice == '3':
            run_persistent_engine(config, argparse.Namespace())
        elif choice == '4':
            safe_async_run(run_batch_prefetch(config), "Pre-Fetch")
        elif choice == '5':
            create_and_launch_link_helper(config)
        elif choice == '6':
            safe_async_run(test_scanner_connections(config), "Connection Test")
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
    config = config_manager.get_config()
    if args.command == 'analyze':
        safe_async_run(run_unified_pipeline(args), "Unified Analysis")
    elif args.command == 'parse':
        run_batch_parse(config, args)
    elif args.command == 'persistent':
        run_persistent_engine(config, args)
    elif args.command == 'collect':
        create_and_launch_link_helper(config)
    elif args.command == 'prefetch':
        safe_async_run(run_batch_prefetch(config), "Pre-Fetch")
    elif args.command == 'test':
        safe_async_run(test_scanner_connections(config), "Connection Test")
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

def create_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Paddock Parser Toolkit v3.0 - A Unified Racing Intelligence Tool",
        epilog="Use '<command> --help' for command-specific options."
    )
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    subparsers.add_parser('analyze', help="Run the full unified analysis")
    subparsers.add_parser('parse', help="Parse local HTML files only")
    subparsers.add_parser('persistent', help="Launch the 'Always-On' live paste engine")
    subparsers.add_parser('collect', help="Generate the manual collection helper page")
    subparsers.add_parser('prefetch', help="Pre-fetch all accessible HTML data sources")
    subparsers.add_parser('test', help="Test all data source connections")

    return parser

# =============================================================================
# --- MAIN EXECUTION ---
# =============================================================================

if __name__ == "__main__":
    try:
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
        logging.info("Application terminated by user.")
    except Exception as e:
        logging.critical(f"A fatal error occurred: {e}", exc_info=True)
        print(f"\n❌ A fatal error occurred: {e}")
        sys.exit(1)
    finally:
        logging.shutdown()
