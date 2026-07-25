# System Architecture & Agent Design 🤖

The **AI LinkedIn Post Generator** is structured as a collection of specialized, highly cohesive **Software Agents** operating under a secure human-in-the-loop coordinator. The codebase maintains strict decoupling between data models, API integrations, and the central event loop.

---

## 🗺️ Multi-Agent Topology

```
                  +--------------------------------+
                  |   User (Telegram Client App)   |
                  +--------------------------------+
                                  |
                                  | Commands & Approvals
                                  v
+------------------+     +-------------------+     +-------------------------+
|  Security Guard  | --> |  Bot Coordinator  | --> |     SQLite Database     |
|   (Filter Dec)   |     |   (src/bot.py)    |     |   (src/db/database.py)  |
+------------------+     +-------------------+     +-------------------------+
                                  |                             ^
                                  | Trigger                     | Status, Url Cache,
                                  v                             | Hist Preferences
+-------------------------------------------------+             |
|                  Curation Agent                 | ------------+
|                (src/curator.py)                 |
+-------------------------------------------------+
                                  |
                                  | Curated Fresh Articles
                                  v
+-------------------------------------------------+
|                  LLM Brain Agent                |
|           (src/llm/providers/base.py)           |
+-------------------------------------------------+
                                  |
                                  | Approved Title/Angle
                                  v
+-------------------------------------------------+
|               Visual Rendering Agent            |
|               (src/renderer.py)                 |
+-------------------------------------------------+
```

---

## 🧩 Agent Roles & Responsibilities

### 1. The Bot Coordinator Agent (`src/bot.py`)
Acts as the central execution scheduler and interface gateway.
* **Responsibilities**:
  * Boots up the system event loops and validates environment credentials at startup.
  * Translates incoming Telegram `/generate` messages into curation commands.
  * Serializes and dispatches generated proposal cards containing interactive callback keyboard keys.
  * Dispatches generated technical copy drafts and matching visual PNG graphic files back to the client.

### 2. The Security Guard Agent (`src/bot.restricting`)
Enforces absolute system and budget integrity.
* **Responsibilities**:
  * Intercepts all incoming webhook and polling signals.
  * Audits caller IDs against the strict `ALLOWED_CHAT_ID` integer constraint.
  * Immediately drops unauthorized interactions silently to prevent resource depletion, prompt manipulation, or credential leakage.

### 3. The Curation Agent (`src/curator.py`)
An automated web-scraping and RSS aggregation microservice.
* **Responsibilities**:
  * Connects to standard news and technical APIs: Hacker News JSON Feed, GitHub Trending web layers, ArXiv XML search indexes, and specialized Reddit RSS boards.
  * Extracts metadata: titles, authors, descriptions, repository stars, dates, and origin links.
  * Standardizes diverse API schemes into cohesive, typing-validated `Article` structures.
  * Interfaces with SQLite to filter out any previously processed URLs, guaranteeing only fresh, unique topics are queued.

### 4. The LLM Brain Agent (`src/llm/`)
Evaluates historical content patterns and handles structured language model tasks.
* **Responsibilities**:
  * Queries SQLite history records for positive feedback (previously approved post structures) and negative constraints (rejected posts).
  * Formulates precise prompts to guide AI topic alignment.
  * Communicates with active AI backends (**Google Gemini** or local **Ollama** clients) to generate structured post proposals.
  * Expands short, approved concepts into comprehensive technical drafts, formatting hooks, bullet points, and marketing hashtags.

### 5. The Visual Rendering Agent (`src/renderer.py`)
A fast web-rendering and image-processing agent.
* **Responsibilities**:
  * Loads local highly aesthetic HTML files pre-compiled with Tailwind CSS and responsive CSS blurs.
  * Injects approved titles, subtitles, and category badges directly into the HTML DOM.
  * Launches headless Playwright browser contexts, waits for stylesheet CDNs and Google Fonts to be painted (`networkidle`), and takes 1200x630 resolution PNG screenshots.
  * Saves pixel-perfect assets to disk for immediate Telegram media delivery.
