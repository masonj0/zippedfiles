# Paddock Parser Toolkit - Agent Development Guide

This document provides high-level guidance for AI agents working on this repository.

## 1. Architectural Strategy: V3 Adapters

The project is moving towards a unified `V3` architecture for all data source adapters. The goal is to create a more robust, stable, and maintainable system.

- **Golden Path:** All new adapters must inherit from `adapters.base_v3.BaseAdapterV3`.
- **Migration:** Existing functional adapters (e.g., Timeform) should be migrated from the legacy V2 pattern to the V3 pattern as a priority.
- **Benefits:** The V3 architecture enforces a cleaner separation of concerns, better configuration management, and more resilient error handling.

## 2. Configuration Management

The `config_settings.json` file is the **single source of truth** for all application settings.

- **Reconciliation:** The `enabled` status for any data source in this file **must** reflect reality. If an adapter is broken, experimental, or non-functional, it must be marked as `"enabled": false`. Add a comment explaining the reason for its disabled state.
- **Centralization:** All configuration constants, including `FINGERPRINTS`, `HTTP_HEADERS`, etc., should be moved from `.py` files into `config_settings.json` to ensure a single, clear location for all settings.

## 3. Advanced Fetching Techniques

The `fetching.py` module contains advanced capabilities for bypassing anti-scraping measures. These should be leveraged for high-value targets.

- **Playwright Bootstrapping:** For adapters targeting sites protected by services like Cloudflare (e.g., Timeform), the `bootstrap_session_with_playwright` function should be integrated into the fetching process. This allows the system to solve JavaScript challenges and acquire valid session cookies.
- **Resilience:** The `ResilientFetcher` class should be used for all HTTP requests to provide automated retries and header rotation.

## 4. Code Quality

The codebase has been cleaned to adhere to standard Python linting rules (PEP8). This level of quality must be maintained. Future work should be checked with a linter to prevent the introduction of new technical debt.
