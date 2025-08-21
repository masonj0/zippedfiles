# Paddock Parser Toolkit: Development Roadmap

## 1. V3 Strategic Pillars

Based on a recent strategic synthesis, our development will be guided by the following core principles to create a more resilient, intelligent, and ethical V3 architecture.

*   **On Defense: Mimicking Human Behavior**
    *   **Core Insight:** Our greatest vulnerability is session and timing predictability. An advanced adversary can detect the non-human rhythm of our fetching patterns.
    *   **Strategic Response:** Introduce more sophisticated randomness—"chaos"—into our timing and session management to break predictable mathematical patterns and more closely mimic the erratic behavior of a real, impatient human.

*   **On Architecture: The Intelligent Ecosystem**
    *   **Core Insight:** A future-proof V3 architecture requires more intelligence throughout the process.
    *   **Strategic Response:** Evolve our thinking from a linear pipeline to a cyclical, intelligent ecosystem. Our next major architectural evolution should focus on adding a **"Contextualize"** stage before scoring (to integrate external data like weather and news) and a **"Feedback"** loop where real race results are used to improve the entire model.

*   **On AI Integration: The Hybrid Approach**
    *   **Core Insight:** The most sophisticated use of an LLM is for **Dynamic Factor Weighting**.
    *   **Strategic Response:** Treat the LLM as a "context provider" that feeds qualitative insights and dynamic weights into our quantitative scoring engine, giving us the best of both worlds. For example, the LLM could analyze pundit commentary for a race and tell the engine to increase the weight for 'jockey experience' by 15%.

*   **On Ethics: The "Dedicated Human Researcher" Test**
    *   **Core Insight:** If a single, extremely dedicated human using browser developer tools could not plausibly achieve the same data collection footprint, our methods are too aggressive.
    *   **Strategic Response:** Formally adopt this principle and reframe our internal language from "scraping warfare" to **"resilient data access,"** a model that reflects a sustainable and ethical long-term strategy.

---

## 2. Implementation Roadmap

This plan is broken down into a clear, step-by-step process.

### Phase 1: Foundational Enhancements (Completed)
This phase involved a full architectural refactoring to create a unified V2 pipeline and the initial V3 foundation (`ConfigurationManager`, `BaseAdapterV3`).

### Phase 2: Advanced Scraping & Resilience
This phase focuses on making our data gathering dramatically more resilient, intelligent, and capable.

**Tier 1: High-Priority Features**
-   **Playwright Bootstrap Integration:**
    -   **Status:** Implemented.
-   **WebSocket Integration for Live Odds:**
    -   **Goal:** Connect directly to the WebSocket streams used by many sites for live odds and market updates.
    -   **Next Steps:** Add `websockets` dependency. Create a `live_ws.py` module and a new type of adapter to handle WebSocket connections.

**Tier 2: Resilience & Stealth Features**
-   **Graceful Degradation:** Enhance `resilient_get` to include fallback logic if advanced fetching fails.
-   **Image OCR as a Backup:** Implement an OCR fallback for sites that render data as images.
-   **Advanced Block Detection:** Augment block detection with timing attacks and content fingerprinting.
-   **Honeypot Detection:** Add a utility to remove invisible scraper traps from HTML.

### Phase 3: Proactive Data Discovery & Strategy
This phase shifts from reactive scraping to proactively discovering new data sources.

-   **Mobile App API Reverse Engineering:** A research task to investigate mobile app APIs, which are often simpler and less protected.
-   **Automated Discovery Tools:**
    -   **Next Steps:** Build utility functions for finding RSS/XML feeds, scanning JS files for API endpoints, and scanning SSL certificates for API subdomains.

---

## 3. Data Source Discovery Leads
This section contains a backlog of promising open-source projects and resources for finding and scraping new data feeds, as provided by the user.

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
