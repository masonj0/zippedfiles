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

## 3. Data Source Discovery Leads
This section contains a backlog of promising open-source projects and resources for finding and scraping new data feeds.

1.  [joenano/rpscrape](https://github.com/joenano/rpscrape) – Scrapes horse racing results and racecards.
2.  [Daniel57910/horse-scraper](https://github.com/Daniel57910/horse-scraper) – Web scraper for horse racing websites.
3.  [Web Scraping for HKJC (Hong Kong Jockey Club)](https://gist.github.com/tomfoolc/ef039b229c8e97bd40c5493174bca839) – Gist for horse racing data scraping.
4.  [LibHunt horse-racing open source projects](https://www.libhunt.com/topic/horse-racing) – Curated list of open source horse racing projects.
5.  [Web data scraping for horse racing & greyhound (blog)](https://www.3idatascraping.com/how-does-web-data-scraping-help-in-horse-racing-and-greyhound/) – Resource and explanation of scraping techniques.
6.  [Fawazk/Greyhoundscraper](https://github.com/Fawazk/Greyhoundscraper) – Python tool to extract greyhound racing data.
7.  [Betfair Hub Models Scraping Tutorial](https://betfair-datascientists.github.io/tutorials/How_to_Automate_3/) – Guide for scraping Betfair model ratings.
8.  [scrapy-horse-racing](https://github.com/chrismattmann/scrapy-horse-racing) – Scrapy-based project for horse racing data.
9.  [horse-racing-data](https://github.com/jeffkub/horse-racing-data) – Historical horse racing data collection and tools.
10. [Greyhound results web scraping code example (StackOverflow)](https://stackoverflow.com/questions/77761268/python-code-to-webscrape-greyhound-resukts-from-gbgb-site-for-soecified-dte-rang) – Discussion and example code for scraping UK greyhound results.
