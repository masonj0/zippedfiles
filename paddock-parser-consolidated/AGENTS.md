### **CRITICAL TOOLING ALERT: Git Branching Limitation**

**All agents must be aware of a recurring bug in the environment's `submit` tool. This is a non-negotiable operational constraint.**

*   **The Bug:** The `submit` command **DOES NOT** correctly create new feature branches as it might claim. If you are working on `feature/task-a` and attempt to submit your work to a new branch called `feature/task-b`, the tool will silently fail to create the new branch. Instead, it will almost always force-push your new commits to the existing branch (`feature/task-a`).

*   **The Implication:** You, the agent, are effectively "handcuffed" to the first branch you start working on for any given task. Do not rely on the `submit` tool's ability to manage multiple branches.

*   **The Official Protocol ("Stay on Mission"):**
    1.  Complete your entire task on a single feature branch.
    2.  Submit your final, complete work to that branch.
    3.  The human project lead will then merge this feature branch into the main branch (`main-1`) via a Pull Request.
    4.  You will then be given a command (`git checkout main-1 && git pull origin main-1`) to re-synchronize your workspace, allowing you to start your next task from a clean, updated foundation by creating a new feature branch.

**Do not deviate from this protocol. Assuming the `submit` tool can create new branches will lead to a corrupted Git history and lost work.**

---
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

#### **Primary Strategic Approach: API-First, GraphQL Priority**

Our reconnaissance has revealed a critical strategic insight: the most valuable and reliable data sources are modern web applications that power their front-ends using internal APIs. HTML scraping is a viable fallback, but **our primary approach should always be to find and leverage these APIs.**

**Our highest priority targets are sites that use GraphQL.**

*   **What is GraphQL?** It is a modern, flexible API technology used by major platforms like FanDuel Racing. Unlike traditional APIs, it uses a single endpoint (e.g., `/graphql`) and receives complex queries in the body of a `POST` request.
*   **Why is it our Priority?** A single GraphQL endpoint can be a gateway to the platform's entire data model, offering a rich, stable, and comprehensive source for thoroughbred, harness, and greyhound data, often all in one place.
*   **Discovery Method:** GraphQL endpoints are discovered using the browser's Developer Tools (Network tab, filtering for Fetch/XHR), identifying `POST` requests to a `/graphql` endpoint, and capturing the request's JSON `body`. This "human-in-the-loop" reconnaissance is the essential first step before an adapter can be built.

**Our goal is to prioritize the discovery and implementation of adapters for GraphQL-powered sites before falling back on traditional REST APIs or HTML scraping.**

-   **Creating a New Adapter:**
    1.  **Perform API-First Reconnaissance:** Before writing any code, the first step is to investigate the target site for a GraphQL or REST API using browser developer tools. This is now the standard first step, preceding any other discovery method.
    2.  **Fallback to RSS/HTML:** If and only if no usable API is found, fall back to other discovery methods like using the `find_rss.py` tool (`paddock_parser/tools/find_rss.py`).
    3.  Create a new file in the `adapters/` directory (e.g., `my_adapter.py`).
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



### **Data Acquisition Protocols**


To align with our API-First strategy, all agents tasked with creating new adapters must follow these protocols.

**1. The Reconnaissance Protocol (Human-Assisted):**
*   The first step for any new data source is a "human-in-the-loop" reconnaissance mission.
*   The primary method is to use a browser's **Developer Tools** (Network tab, filtering for **Fetch/XHR**) to find internal API calls.
*   The highest priority is to identify **GraphQL (`/graphql`) endpoints**.
*   The required intelligence to be gathered is the **Request URL**, all necessary **Headers**, and the complete **Request Body (JSON)** for both the "list" and "detail" stages of the process.

**2. The Archeology Protocol (Handling Old Libraries):**
*   If an agent discovers an old, unmaintained open-source library for a target site (an "archeological map"), it must **NOT** attempt to install or fix the old library.
*   Instead, the agent's task is to **analyze the old library's source code** to understand the old API's logic.
*   The agent will then use this knowledge to assist the human researcher in performing the **Reconnaissance Protocol** on the *modern* website.
*   This protocol ensures we learn from past work without getting bogged down by outdated technology.

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


### **Emergency Communication Protocol: The Chat Handoff**

In the event of a **catastrophic environmental failure**, an agent's standard tools (`submit`, `write_file`) may become completely non-functional. The agent may report that it cannot save its work or communicate through standard file-based handoffs.

This is a "Level 3" failure. When this occurs, we will revert to the most reliable communication channel available: the direct chat interface.

**Protocol Steps:**

1.  **Agent Declaration:** The agent must recognize that its core tools have failed and declare a "Level 3 Failure." It should state that it is unable to write a `HANDOFF_DOCUMENT.md` and will provide its final report via chat.

2.  **Human Request:** The human project lead will then issue a direct command, such as: "Please provide your complete Handoff Document as a direct reply in this chat."

3.  **Chat Handoff:** The agent will then format its complete handoff document (summarizing its successes, the final blocker, and recommendations for the next agent) as a single, well-formatted text message and send it as a reply.

This protocol ensures that even in the case of a total environmental collapse, the agent's valuable "institutional knowledge" is never lost. It is our ultimate safety net.


### **CRITICAL PROTOCOL: The Authenticity of Sample Data**

It has been discovered that a previous agent exhibited a critical failure mode: it would use "fake" or "placeholder" sample data (e.g., copying a sample from a different adapter) to build and test a new adapter. This is a **Level 1 Critical Error** as it completely invalidates the purpose of unit testing.

**The Authenticity Protocol:**

1.  **Sample Data Must Be Authentic:** All sample HTML or JSON files used for testing an adapter **must** be the authentic, unmodified output from the adapter's specific target website or API.

2.  **Human-in-the-Loop for Sample Provision:** For all new adapters, the "human-in-the-loop" will be responsible for providing the initial, authentic sample data file. The agent's first step is to request this file if it is not already present.

3.  **Verification is Mandatory:** If an agent suspects that a sample file is incorrect, outdated, or inauthentic, its primary mission is to **stop all development** on the adapter and immediately report the data mismatch to the human project lead. This is not a blocker; this is a critical and required quality assurance step.

**An adapter that is "proven" to work with fake data is a fundamentally broken adapter. Adherence to this protocol is non-negotiable.**
