# AGENTS.md: Instructions for AI Assistants

Hello, fellow agent! This document provides guidance for working on the Paddock Parser Toolkit. This project has recently undergone a major refactoring to a unified V2 architecture. Please adhere to the following principles.

## 1. Project Architecture Overview

The application is a racing intelligence toolkit that gathers data from various web sources and local files, normalizes it, scores it, and presents the results. The architecture is now unified around a central data pipeline and a consistent data model.

- **Data Flow:** The main pipeline (`main.py:run_unified_pipeline`) orchestrates the process:
    1.  Data is fetched from live web sources via **V2 Adapters**.
    2.  Data is parsed from local HTML files via the **Legacy Parser**.
    3.  All data is converted into a standard `NormalizedRace` object.
    4.  The combined data is merged, scored by the `V2Scorer`, and reported.

## 2. Key Modules and Their Purpose

-   `main.py`: The main entry point for the application. Contains the user-facing menu (`main_menu`) and CLI (`main_cli`), and orchestrates the unified pipeline.
-   `analysis.py`: Contains the core V2 pipeline logic, including the `V2Scorer` and functions for processing and scoring race data.
-   `normalizer.py`: The **single source of truth** for data models. All race data MUST be normalized into the `NormalizedRace` and `NormalizedRunner` dataclasses defined here.
-   `paddock_parser.py`: This module handles parsing of local HTML files and data pasted to the clipboard. It has been refactored to convert its output into the standard `NormalizedRace` model.
-   `racing_data_parser.py`: This is a lower-level parsing library used by `paddock_parser.py`. It contains "surgical parsers" for specific website HTML structures.

### The `adapters` Package

-   **Purpose:** The `adapters/` directory is for all V2 live data source integrations. Each adapter is responsible for fetching and parsing data from a single web source (API or HTML).
-   **Creating a New Adapter:**
    1.  Create a new file in the `adapters/` directory (e.g., `my_adapter.py`).
    2.  Create a new class that inherits from `BaseV2Adapter`.
    3.  Set a unique `source_id` class attribute.
    4.  Implement the `async def fetch(self)` method. This method must return a `list[RawRaceDocument]`.
    5.  Decorate your class with `@register_adapter`. The `adapters/__init__.py` file will automatically discover and register it.

## 3. Development Conventions

-   **Unified Data Model:** ALWAYS use the `NormalizedRace` and `NormalizedRunner` dataclasses from `normalizer.py` for all race data processing. Do not introduce new, duplicative data structures.
-   **Centralized Scoring:** All scoring MUST be done using the `V2Scorer` class from `analysis.py`.
-   **Dependencies:** All new dependencies must be added to the `requirements.txt` file.

## 4. Testing

-   The project has a test suite. The main test file is `test_v2_scorer.py`.
-   To run the tests, first ensure all dependencies are installed (`pip install -r requirements.txt`), then run:
    ```bash
    python -m unittest test_v2_scorer.py
    ```
-   Before submitting any work, please ensure all tests pass without any import errors or failures.
