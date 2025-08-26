# AGENTS.md: Instructions for AI Assistants

Hello, fellow agent! This document provides guidance for working on the Paddock Parser Toolkit. This project has recently undergone a major refactoring to a unified V2 architecture. Please adhere to the following principles.

## 1. Core Architectural Principles

*   **Library-First Design:** The `paddock-parser` package is not just a single application; it is a reusable library. All new features, such as the web dashboard or mobile agent, should be built as clients of this core library. The `portable-demo.py` script serves as a good example of this client-server architecture.
*   **Ethical Data Access:** We adhere to the "Dedicated Human Researcher" test. If a single, dedicated human using browser developer tools could not plausibly achieve the same data collection footprint, our methods are too aggressive. Our approach is "resilient data access," not "scraping warfare."

## 2. Project Architecture Overview

The application is a racing intelligence toolkit that gathers data from various web sources and local files, normalizes it, scores it, and presents the results.

- **Data Flow:** The main pipeline (`main.py:run_unified_pipeline`) orchestrates the process:
    1.  Data is fetched from live web sources via **V2 Adapters**.
    2.  Data is parsed from local HTML files via the **Legacy Parser**.
    3.  All data is converted into a standard `NormalizedRace` object.
    4.  The combined data is merged, scored by the `V2Scorer`, and reported.

## 3. Key Modules and Their Purpose

-   `main.py`: The main entry point for the application. Contains the user-facing menu (`main_menu`) and CLI (`main_cli`), and orchestrates the unified pipeline.
-   `analysis.py`: Contains the core V2 pipeline logic, including the `V2Scorer` and functions for processing and scoring race data.
-   `normalizer.py`: The **single source of truth** for data models. All race data MUST be normalized into the `NormalizedRace` and `NormalizedRunner` dataclasses defined here.
-   `paddock_parser.py`: This module handles parsing of local HTML files and data pasted to the clipboard. It has been refactored to convert its output into the standard `NormalizedRace` model.
-   `racing_data_parser.py`: This is a lower-level parsing library used by `paddock_parser.py`. It contains "surgical parsers" for specific website HTML structures.

### The `adapters` Package

-   **Purpose:** The `adapters/` directory is for all V2 live data source integrations. Each adapter is responsible for fetching and parsing data from a single web source (API or HTML).
-   **Creating a New Adapter:**
    1.  **Discover Data Sources:** Before writing code, use the `find_rss.py` tool (`paddock_parser/tools/find_rss.py`) to automatically scan websites for potential RSS/XML data feeds. This is a standard first step.
    2.  Create a new file in the `adapters/` directory (e.g., `my_adapter.py`).
    3.  Create a new class that inherits from `BaseAdapterV3`.
    4.  Set a unique `source_id` class attribute.
    5.  Implement the `async def fetch(self)` method. This method must return a `list[RawRaceDocument]`.
    6.  Decorate your class with `@register_adapter`. The `adapters/__init__.py` file will automatically discover and register it.

## 4. Development Conventions

-   **Unified Data Model:** ALWAYS use the `NormalizedRace` and `NormalizedRunner` dataclasses from `normalizer.py` for all race data processing. Do not introduce new, duplicative data structures.
-   **Centralized Scoring:** All scoring MUST be done using the `V2Scorer` class from `analysis.py`.
-   **Dependencies:** All new dependencies must be added to the `requirements.txt` file.
-   **Standardized Core Utilities:** Core, shared functions (like `resilient_get` in `fetching.py`) must have clear, stable, and well-documented function signatures to prevent errors as more adapters are built. Avoid passing the entire config dictionary when only specific values are needed.
-   **Proactive Scraper Defense:** When building HTML-based adapters, use the `remove_honeypots` utility to strip out invisible scraper traps from the HTML before parsing. This is a critical step for long-term viability.

## 5. Testing

-   The project has a test suite. The main test file is `test_v2_scorer.py`.
-   To run the tests, first ensure all dependencies are installed (`pip install -r requirements.txt`), then run:
    ```bash
    python -m unittest test_v2_scorer.py
    ```
-   For adapter-specific tests, `pytest` is preferred. Use the following command, which sets the `PYTHONPATH` correctly to avoid import issues:
    ```bash
    PYTHONPATH=/app/paddock-parser-consolidated/ python3 -m pytest /app/paddock-parser-consolidated/paddock_parser/adapters/tests/your_test_file.py
    ```
-   Before submitting any work, please ensure all relevant tests pass without any import errors or failures.
