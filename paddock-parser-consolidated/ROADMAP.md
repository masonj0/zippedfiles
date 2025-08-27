# Paddock Parser Toolkit: Development Roadmap

## 1. V3 Strategic Pillars

Our development is guided by core principles to create a resilient, intelligent, and ethical V3 architecture.

*   **On Defense: Mimicking Human Behavior & Proactive Defense**
    *   **Core Insight:** Our greatest vulnerability is predictability. Advanced adversaries can detect non-human fetching patterns and use scraper traps (honeypots).
    *   **Strategic Response:** Introduce sophisticated randomness ("chaos") into timing and session management. Proactively scan for and remove invisible "honeypot" links before parsing to avoid detection.

*   **On Architecture: The Intelligent Ecosystem & Library-First Design**
    *   **Core Insight:** A future-proof architecture requires intelligence and reusability.
    *   **Strategic Response:** Evolve from a linear pipeline to a cyclical, intelligent ecosystem. The `paddock-parser` package should be treated as a reusable library, enabling other tools (like the mobile agent) to easily use the core parsing and scoring logic.

*   **On AI Integration: The Hybrid Approach**
    *   **Core Insight:** The most sophisticated use of an LLM is for **Dynamic Factor Weighting**.
    *   **Strategic Response:** Treat the LLM as a "context provider" that feeds qualitative insights and dynamic weights into our quantitative scoring engine.

*   **On Ethics: The "Dedicated Human Researcher" Test**
    *   **Core Insight:** If a single, dedicated human using browser developer tools could not plausibly achieve the same data collection footprint, our methods are too aggressive.
    *   **Strategic Response:** Formally adopt this principle, reframing our approach as **"resilient data access"** for a sustainable and ethical long-term strategy.

---

## 2. Implementation Roadmap

### Phase 1: Core Data Acquisition & Resilience
This phase focuses on making our data gathering dramatically more resilient, intelligent, and capable.

-   **Automated Data Source Discovery:**
    -   **Goal:** Move from manually finding data sources to proactively discovering new ones.
    -   **Next Steps:** Regularly use the `find_rss.py` utility as a standard step before building any new adapter.

-   **Proactive Scraper Defense (Honeypot Detection):**
    -   **Goal:** Massively increase the long-term viability and stealth of the toolkit by proactively avoiding scraper traps.
    -   **Next Steps:** This is a foundational task. A utility to scan HTML for invisible "honeypot" links and remove them should be implemented and used by all HTML-based adapters.

-   **Graceful Degradation:**
    -   **Goal:** Enhance `resilient_get` to include fallback logic if advanced fetching fails.

-   **Image OCR as a Backup:**
    -   **Goal:** Implement an OCR fallback for sites that render data as images.

### Phase 2: Advanced Scraping & Real-Time Data
This phase transitions the toolkit from a batch-processing scraper to a real-time streaming data engine.

-   **Real-Time Data via WebSocket Adapter:**
    -   **Goal:** This is a paradigm shift for the toolkit. Connect directly to `wss://` WebSocket streams to receive real-time odds data, which is essential for capturing market movements.
    -   **Next Steps:** Add `websockets` dependency. Create a new type of adapter to handle WebSocket connections, identify target endpoints, and parse incoming messages.

-   **Playwright Bootstrap Integration:**
    -   **Status:** Implemented. This hybrid approach uses a real browser to establish an authenticated session, then passes cookies to `httpx` for faster scraping.

### Phase 3: Intelligence & Analysis
This phase focuses on enriching the data and improving the scoring model.

-   **Contextualization Engine:**
    -   **Goal:** Add a "Contextualize" stage to the pipeline before scoring to integrate external data like weather, news, and pundit commentary.
    -   **Next Steps:** Design a system to fetch and align external data points with specific races.

-   **Results-Based Feedback Loop:**
    -   **Goal:** Create a feedback loop where real race results are used to automatically improve the scoring model and adapter accuracy over time.
    -   **Next Steps:** Develop a mechanism to ingest race results and a model training process to adjust `V2Scorer` weights.

### Phase 4: User Interface & Delivery
This phase focuses on the end-user delivery of the toolkit's intelligence.

-   **The Autonomous Mobile Agent:**
    -   **Goal:** Realize the vision of a pocket-sized, self-contained intelligence agent, not just a web dashboard.
    -   **Next Steps:** Refactor the `mobile_alert_engine.py` to use the `spectral_scheduler` for its main loop, turning it into a lightweight, autonomous agent for mobile devices (e.g., via Termux) to provide real-time alerts. This is the guiding principle for notification-based features.

-   **Webhook/Push Integration:**
    -   **Goal:** Allow external services like IFTTT or Zapier to trigger scans instantly.
    -   **Next Steps:** Enhance `mobile_alert_engine.py` with a lightweight HTTP server (e.g., using `aiohttp`) to listen for incoming webhooks.

---

### **Primary Strategic Approach: API-First, GraphQL Priority**

Our reconnaissance has revealed a critical strategic insight: the most valuable and reliable data sources are modern web applications that power their front-ends using internal APIs. HTML scraping is a viable fallback, but our primary approach should always be to find and leverage these APIs.

**Our highest priority targets are sites that use GraphQL.**

*   **What is GraphQL?** It is a modern, flexible API technology used by major platforms like FanDuel Racing. Unlike traditional APIs, it uses a single endpoint (e.g., `/graphql`) and receives complex queries in the body of a `POST` request.
*   **Why is it our Priority?** A single GraphQL endpoint can be a gateway to the platform's entire data model, offering a rich, stable, and comprehensive source for thoroughbred, harness, and greyhound data, often all in one place.
*   **Discovery Method:** GraphQL endpoints are discovered using the browser's Developer Tools (Network tab, filtering for Fetch/XHR), identifying `POST` requests to a `/graphql` endpoint, and capturing the request's JSON `body`. This "human-in-the-loop" reconnaissance is the essential first step before an adapter can be built.

**Our goal is to prioritize the discovery and implementation of adapters for GraphQL-powered sites before falling back on traditional REST APIs or HTML scraping.**

### **Data Source Discovery: From Scraping to Intelligence Gathering**

Our recent reconnaissance efforts have yielded a significant breakthrough in our data acquisition strategy. We have confirmed that the most valuable, reliable, and data-rich sources are modern web platforms that use internal **GraphQL APIs**.

Our strategic priority has therefore shifted. We are now focused on an **API-First** approach. This elevates our data acquisition from opportunistic scraping to targeted intelligence gathering.

#### **Tier 1: Confirmed Live GraphQL Targets**

These are our highest-priority targets, where a live API has been identified and is ready for adapter implementation.

*   **Target:** **FanDuel Racing**
    *   **API Type:** GraphQL
    *   **Status:** **Confirmed Live.** Two-stage query process discovered (schedule and race detail).
    *   **Value:** A single integration point for high-quality **Thoroughbred** and **Harness Racing** data for the US market. This is our primary active development target for the "Variety" mission.

#### **Tier 2: High-Potential Leads for Investigation**

These are leads identified through research that are likely to have modern, public-facing APIs. They require a "human-in-the-loop" reconnaissance mission to confirm.

*   **Target:** **The Odds API (`the-odds-api.com`)**
    *   **Potential:** A commercial odds aggregator. Could be a "one-to-many" source, providing odds from dozens of bookmakers in a single feed. A potential goldmine for Phase 2 (Advanced Odds Processing).
    *   **Mission:** Investigate developer documentation for horse racing coverage and free tier limitations.

*   **Target:** **Prophet Exchange API (`github.com/prophet-exchange`)**
    *   **Potential:** A betting exchange with a public GitHub presence, signaling a developer-friendly API. Exchanges are excellent sources for real-time market data.
    *   **Mission:** Investigate API documentation for horse racing coverage and technology type (REST, GraphQL, WebSocket).

#### **Tier 3: The "Project Archeology" Protocol**

This protocol is for leveraging old, unmaintained open-source projects as "treasure maps" to modern APIs. The discovery of `PySBR` (a dead project for a deprecated feature) taught us this valuable lesson.

*   **The Principle:** Old API wrappers are not to be revived. They are to be studied as blueprints of how a site's API *used to work*.
*   **The Mission:** When an "archeological" lead is found, the task is to perform reconnaissance on the *modern* version of the target website to find the *new* API, using the old code as a guide. This prevents wasting time on dead ends and accelerates the discovery of their modern replacements.

---

## **The "Polyglot Future" Vision**

The long-term vision for the Paddock Parser Toolkit is to evolve beyond a single-language "monolith" and into a "polyglot" system, where we use the absolute best language for each specific task. This will allow the toolkit to become more powerful, scalable, and performant than it could ever be if it remained purely in Python.

The proposed architecture identifies three distinct roles:
1.  **The "Project Lead" (Python):** The central nervous system for orchestration, data science, and high-level analysis.
2.  **The "Foragers" (Go/Rust):** A high-performance, standalone data ingestion engine for maximum concurrency and speed.
3.  **The "Town Crier" (TypeScript):** An interactive, web-based user interface for modern data presentation and real-time dashboards.

### **Architectural Considerations**

As we move towards this vision, the following key points, based on agent feedback, must be considered:

*   **Challenge - The API Contract:** The single most critical success factor will be the design of the **API contracts** between the three components. These APIs (e.g., between Python/TypeScript and Python/Go) must be meticulously designed, documented, and versioned to allow for independent development and prevent integration issues.

*   **Opportunity - Enhancing the "Forager" Role:** The "Foragers" could be made even more powerful by performing a "pre-parsing" step. For example, a Go-based forager could extract a specific JSON blob from a large HTML page and return only that small chunk to Python, further reducing the load on the Python brain.

*   **Challenge - Operational Complexity:** Moving from a single application to three separate services significantly increases the complexity of development, testing, and deployment. A strategy for managing this, likely involving containerization (Docker) and local orchestration (Docker Compose), will be essential.
