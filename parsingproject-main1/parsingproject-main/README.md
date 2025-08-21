# Paddock Parser Toolkit v2.0

This project is a powerful, unified toolkit for gathering, analyzing, and scoring global horse racing data. It has been refactored to a modern v2.0 architecture that combines live data fetching with local file parsing in a single, seamless pipeline.

## Core Features

-   **Unified Analysis Pipeline:** The `main.py analyze` command orchestrates the entire workflow, gathering data from all available sources, merging it, scoring it, and generating reports.
-   **Extensible Adapter Architecture:** The toolkit now uses a modular adapter pattern (`adapters/`) to fetch data from live web sources (APIs and HTML). This makes adding new data sources clean and straightforward.
-   **Advanced Scraping:** The fetching engine is highly resilient, featuring browser fingerprint rotation, configurable request delays, and automatic retries to avoid blocks.
-   **Local File & Clipboard Parsing:** The toolkit retains its powerful "Deep Dive" capabilities. It can parse a directory of local HTML files or accept data pasted directly into the "Live Paste Engine" for sources that are difficult to automate.
-   **Centralized Scoring & Normalization:** All data, regardless of its source, is converted into a standard `NormalizedRace` object and scored by a single, central `V2Scorer`. This ensures consistency across all analysis.
-   **Rich Configuration:** The new `config.json` (v2.0 schema) provides granular control over scraping behavior, data sources, and scoring weights, allowing for easy tuning without code changes.

## Quick Start

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure:**
    -   Review and customize `config.json`. Enable the adapters you want to use in the `DATA_SOURCES_V2` section.
    -   To use the local file parser, place your HTML files in the `html_input` directory (or the directory specified by `INPUT_DIR` in the config).
3.  **Run Analysis:**
    -   For a comprehensive run using both live adapters and local files, use the `analyze` command:
        ```bash
        python main.py analyze
        ```
    -   To run the interactive menu, simply run the script with no arguments:
        ```bash
        python main.py
        ```
    -   The main menu provides access to all features, including the Live Paste Engine and data collection tools.

## Mobile Alerting Engine

The project also includes a standalone `mobile_alert_engine.py`. This is a lightweight, autonomous agent designed to run on a mobile device (e.g., via Termux) to provide real-time alerts for high-value racing opportunities. See the internal comments in that file for more details on its usage.
