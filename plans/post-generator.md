# Plan: AI LinkedIn Post Generator

> Source PRD: PRD.md

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes / Bot Commands**: 
  - `/start` - Initial welcome and info.
  - `/generate` - Manual trigger for the curation and proposal generation flow.
  - Callback queries: `approve_<id>`, `reject_<id>`, `skip_<id>` to handle user interactions on individual proposal messages.
- **Schema**: 
  - SQLite database (`history.db`) with a `proposals` table (columns: `id`, `url`, `title`, `source`, `summary`, `proposed_title`, `proposed_angle`, `status`, `created_at`). Already defined in `src/db/database.py`.
- **Key models**: 
  - `Article` - Raw curated news item with `title`, `url`, `source`, `summary`, `score`, `date`.
  - `Proposal` - Saved DB model mapping a curated article to generated titles/angles and tracking approval status.
- **Third-Party Service Boundaries**:
  - **Telegram**: Handled via `python-telegram-bot` with polling. Secured with a decorator verifying `ALLOWED_CHAT_ID`.
  - **AI Provider**: Base class `BaseProvider` with implementations for `GeminiProvider` and `OllamaProvider`.
  - **Curation Feeds**: HTTP integrations using `requests` and `BeautifulSoup` for GitHub Trending, Hacker News API, ArXiv API, and Reddit RSS.
  - **Graphics Engine**: Playwright launching a local HTML template using Tailwind CSS via CDN.

---

## Phase 1: News Curation Pipeline & DB Integration

**User stories**: 
- As a user, I want the bot to fetch the top current articles from Hacker News, GitHub Trending, ArXiv, and Reddit, so that I have a diverse pool of high-quality technical content to choose from.
- As a user, I want the system to filter out articles it has already proposed to me in the past, so that I don't waste time reviewing duplicate content.

### What to build

A standalone curator module (`src/curator.py`) capable of pulling top articles from external news feeds:
- Hacker News: via the official Firebase JSON API (fetching top stories and retrieving details) or Algolia search API.
- GitHub Trending: via scraping the trending page or using a public API wrapper.
- ArXiv: via the official ArXiv Atom feed / API for technical papers.
- Reddit: via the RSS feed of tech-focused subreddits (e.g., `r/machinelearning`, `r/datascience`) without requiring API keys.

The curator should return a unified list of `Article` objects. It must filter out any URLs already present in the database by calling `db.url_exists(url)` and return only fresh content.

### Acceptance criteria

- [ ] Fetching from Hacker News returns a list of active top articles.
- [ ] Fetching from GitHub Trending retrieves trending repository details (name, description, URL).
- [ ] Fetching from ArXiv retrieves recent papers in specific categories (e.g., computer science, AI).
- [ ] Fetching from Reddit RSS retrieves top hot posts from designated technical subreddits.
- [ ] All feeds are normalized into standard `Article` models.
- [ ] Curated articles that already exist in the database (verified via SQLite) are filtered out automatically.
- [ ] A CLI script (`python -m src.curator`) successfully runs the curation and prints filtered article lists.

---

## Phase 2: Core LLM Generation & Preference Learning Loop

**User stories**:
- As a developer, I want to configure the AI provider via an environment variable (`LLM_PROVIDER`), so that I can easily switch between Google Gemini and a local Ollama model.
- As a user, I want to use a local Ollama model (like Llama 3), so that I can run the generation entirely locally without incurring API costs or sharing data externally.
- As a user, I want to use Google Gemini, so that I can leverage a highly capable, fast, and structured LLM for post generation.
- As a user, I want my rejected proposals to be saved in a database, so that the AI can use them as negative constraints in future prompts and learn my preferences.
- As a user, I want my approved proposals to be saved in a database, so that the AI can use them as positive examples to generate content more aligned with my tastes.

### What to build

An extensible LLM integration layer allowing seamless switching between Google Gemini and Ollama:
- Base class `BaseProvider` in `src/llm/base.py`.
- `GeminiProvider` in `src/llm/providers/gemini.py` using `google-generativeai`.
- `OllamaProvider` in `src/llm/providers/ollama.py` using the `ollama` client library.
- Prompts that dynamically query recently approved posts (as positive examples) and rejected posts (as negative constraints / feedback) from SQLite and append them to the system instructions.
- A generation orchestrator that takes clean, curated articles and generates 3-5 distinct `Proposal` elements (each containing a proposed post title and brief post angle/concept).

### Acceptance criteria

- [ ] Provider interface abstract class `BaseProvider` defines consistent methods for generating proposals and final post text.
- [ ] `GeminiProvider` correctly initializes with `GEMINI_API_KEY` and handles JSON/structured output.
- [ ] `OllamaProvider` correctly connects to `OLLAMA_HOST` and formats prompt instructions to guarantee structured responses.
- [ ] System prompt dynamically injects recent approved posts as "style/topic guidelines" and rejected posts as "what to avoid".
- [ ] Generation pipeline takes a list of raw articles and outputs 3–5 well-formed proposal suggestions.
- [ ] A CLI script (`python -m src.generate_proposals`) runs generation using the active provider and prints output.

---

## Phase 3: Telegram Bot Core & Security Protection

**User stories**:
- As a user, I want to send a command (e.g., `/generate`) to my Telegram bot, so that I can trigger the daily news curation and proposal process on demand.
- As a user, I want the bot to present 3 to 5 distinct LinkedIn post proposals in my Telegram chat, so that I have multiple options and angles for my daily post.
- As a user, I want each proposal message to have interactive `[Approve]`, `[Reject]`, and `[Skip]` buttons, so that I can easily make decisions directly within the Telegram UI.
- As a user, I want the Telegram bot to strictly enforce an `ALLOWED_CHAT_ID` check, so that unauthorized individuals cannot interact with my bot, access my data, or consume my API quota.

### What to build

The interactive Telegram Bot client interface:
- A python script (`src/bot.py`) that boots up the bot using `python-telegram-bot` in polling mode.
- An authorization decorator/middleware that intercepts every command/callback and immediately drops the connection if the chat ID does not match `ALLOWED_CHAT_ID` in `src/config.py`.
- `/generate` handler that:
  1. Triggers curation (Phase 1).
  2. Submits curated articles to the active LLM provider (Phase 2).
  3. Saves proposals to the SQLite DB with status `pending`.
  4. Dispatches each proposal as a distinct message in the Telegram chat with inline keyboard buttons: `[Approve]`, `[Reject]`, and `[Skip]`.
- Callback query handlers that update the database status of the corresponding proposal when the user taps any of the buttons.

### Acceptance criteria

- [ ] Security check blocks any interaction from telegram accounts not matching `ALLOWED_CHAT_ID`.
- [ ] `/generate` command coordinates the entire flow of fetching news, generating proposals, and saving them.
- [ ] Each proposal is displayed as a clean message detailing the original article and the proposed post concept, equipped with inline buttons.
- [ ] Clicking `[Reject]` immediately updates the DB status to `rejected` and edits the message to indicate rejection.
- [ ] Clicking `[Skip]` immediately updates the DB status to `skipped` and edits the message to indicate skipping.
- [ ] Robust error handling for cases where no news is available or LLM generation fails.

---

## Phase 4: Beautiful Tailwind Graphic Renderer

**User stories**:
- As a user, I want the bot to automatically generate a beautiful, modern graphic using Tailwind CSS and Playwright when I approve a post, so that my LinkedIn content stands out visually.

### What to build

A visual assets generation engine:
- A local HTML template file (`src/templates/graphic.html`) using modern typography, gradients, card layouts, and Tailwind CSS loaded via CDN.
- A Python rendering module (`src/renderer.py`) using `playwright.async_api`.
- The renderer loads the HTML template locally, dynamically injects the chosen post title and subtitle into the DOM via JavaScript injection, sets an appropriate viewport size (e.g., 1200x630 or 1080x1080 for LinkedIn), and captures a pixel-perfect PNG screenshot saved to `POSTS_DIR`.

### Acceptance criteria

- [ ] HTML/Tailwind template supports responsive and centering typography, modern gradients, and placeholder spots for titles.
- [ ] Renderer successfully initializes headless Playwright.
- [ ] Renderer loads the template, injects custom text (title, subtitle/author tag), and captures a high-resolution PNG image.
- [ ] Generated image is saved locally and is visually complete, modern, and aligned with standard high-quality social graphics.
- [ ] A CLI script/test (`python -m src.renderer`) verifies rendering of a mock graphic file.

---

## Phase 5: Complete Post-Approval Delivery Workflow

**User stories**:
- As a user, I want the bot to send the final generated Markdown text and the rendered PNG image back to my Telegram chat, so that I can easily save the image and copy the text to publish on LinkedIn.

### What to build

The final integration piece linking the user's approval action to final content delivery:
- An callback query handler for `approve_<id>`:
  1. Marks the proposal as `approved` in the SQLite database.
  2. Sends a prompt to the active LLM provider (Phase 2) to generate the *full* final engaging Markdown text for the LinkedIn post based on the approved title/angle.
  3. Triggers Phase 4 to render the accompanying graphic image.
  4. Delivers the final Markdown text and the generated PNG back to the Telegram chat.

### Acceptance criteria

- [ ] Clicking `[Approve]` updates the SQLite status to `approved`.
- [ ] LLM provider successfully expands the brief approved angle into a complete, professional, Markdown-formatted LinkedIn post with hashtags.
- [ ] Playwright engine renders the post graphic with the approved title.
- [ ] Both the complete post copy and the beautiful image are sent directly to the Telegram user in a single, convenient layout or sequential messages.
- [ ] End-to-end integration operates seamlessly under actual or mock inputs.
