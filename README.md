# AI LinkedIn Post Generator Bot 🤖

A secure, autonomous Telegram Bot that curates top tech news, generates engaging LinkedIn post drafts using Google Gemini or local Ollama models, learns from your feedback, and renders modern social graphics using Tailwind CSS and Playwright. It keeps the "human-in-the-loop" for final approvals via mobile-friendly interactive buttons.

---

## 🚀 How to Run Locally

### 1. Prerequisites
- **Python 3.10 to 3.13** installed on your system.
- A **Telegram Bot Token** (obtainable via [@BotFather](https://t.me/BotFather) on Telegram).
- Your **Telegram Chat ID** (obtainable via [@userinfobot](https://t.me/userinfobot) or [@raw_data_bot](https://t.me/raw_data_bot) to restrict bot access to yourself).
- An **LLM Provider**:
  - **Local Ollama (Recommended)**: Free and runs entirely on your machine.
    1. Install Ollama from [ollama.com](https://ollama.com).
    2. Start Ollama: `ollama serve` (or launch the Ollama app).
    3. Pull your preferred model (e.g., `ollama pull hermes3` or `ollama pull llama3.1`).
  - **Google Gemini**: Get an API key from [Google AI Studio](https://aistudio.google.com/).

---

### 2. Setup Instructions

#### Step A: Navigate to the Project Directory
```bash
cd ai-linkedin-automation
```

#### Step B: Create and Activate Virtual Environment
```bash
# Create Virtual Environment
python3 -m venv .venv

# Activate Virtual Environment (macOS/Linux)
source .venv/bin/activate

# On Windows (Command Prompt / PowerShell)
# .venv\Scripts\activate
```

#### Step C: Install Dependencies & Headless Browser
```bash
# Install Python packages
pip install -r requirements.txt

# Install Playwright Chromium binary for social card rendering
playwright install chromium
```

#### Step D: Configure your `.env` File
Copy the example environment configuration:
```bash
cp .env.example .env
```

Open `.env` in a text editor and fill in your details:
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
ALLOWED_CHAT_ID=123456789

# LLM Configuration ('ollama' or 'gemini')
LLM_PROVIDER=ollama

# Ollama Settings (if LLM_PROVIDER=ollama)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=hermes3

# Gemini Settings (if LLM_PROVIDER=gemini)
# GEMINI_API_KEY=your_gemini_api_key_here

# Storage Settings (defaults)
DATABASE_PATH=history.db
POSTS_DIR=./posts
```

---

### 3. Launching the Telegram Bot

Make sure your virtual environment is active (`source .venv/bin/activate`), then start the bot:
```bash
python -m src.bot
```

Once running:
1. Open your bot on Telegram and type `/start`. If your Telegram Chat ID matches the `ALLOWED_CHAT_ID` env variable, the bot will welcome you. (Unauthorized users are ignored silently).
2. Send the `/generate` command to kick off news curation and proposal creation.
3. Review the proposal cards sent to you and tap **Approve 👍**, **Reject 👎**, or **Skip ➡️** directly in Telegram.
4. Tapping **Approve** will automatically generate the final professional post copy and a beautiful visual graphic card, returning both assets directly to your chat for easy copy-pasting to LinkedIn!

---

### 4. Running the Pipelines & Utilities Independently

Our modular architecture allows you to run and test individual slices of the system directly from the command line:

#### A. Run the News Curation Agent
Pulls fresh posts from Hacker News, GitHub Trending, ArXiv, Reddit, Lobsters, InfoQ, Netflix Tech Blog, and Shopify Engineering Blog, filters out already-processed URLs, and prints the fresh items:
```bash
python -m src.curator
# Or target specific source(s) and fetch limit:
python -m src.curator --source shopify --limit 5
python -m src.curator --source netflix,shopify --limit 3
```

#### B. Run the Proposal Generation Agent (LLM Integration)
Curates articles, queries your SQLite database for past feedback and preferences, and generates structured concepts:
```bash
python -m src.generate_proposals
# Or target specific source(s) and proposal count:
python -m src.generate_proposals --source shopify --count 2
python -m src.generate_proposals --source netflix,hn --count 4
```

#### C. Run the Tailwind Graphics Renderer
Renders mock post variables into modern glassmorphic cards and outputs a 1200x630 PNG screenshot to `posts/cli_test_graphic.png`:
```bash
python -m src.renderer
```

---

### 5. Troubleshooting & Tips

- **Unauthorized access blocked**: If the bot ignores commands or logs `Unauthorized access blocked from chat ID`, message [@userinfobot](https://t.me/userinfobot) to verify your exact numeric user ID and set it as `ALLOWED_CHAT_ID` in `.env`.
- **Ollama Connection Refused**: Ensure Ollama is running (`curl http://localhost:11434/api/tags` to test) and the model in `OLLAMA_MODEL` has been pulled with `ollama pull <model_name>`.
- **Playwright / Browser missing**: If rendering fails, ensure you ran `playwright install chromium`.
- **Import errors**: Always run modules using `python -m src.<module_name>` with `.venv` activated.

---

## 🤖 Telegram Bot Commands

Once your Telegram Bot is live and connected, the following commands are available to help you curate, generate, train, and manage your LinkedIn post drafts:

| Command | Usage / Example | Description |
| :--- | :--- | :--- |
| `/start`, `/help` | `/help` | Initial greeting, help manual, and instructions screen listing all commands and usage. |
| `/generate` | `/generate`<br>`/generate 5`<br>`/generate shopify`<br>`/generate shopify 2`<br>`/generate netflix,cloudflare 4`<br>`/generate help` | Generates post proposals. Supports targeting specific tech sources or blogs (26 total: `hn`, `gh`, `arxiv`, `reddit`, `lobsters`, `infoq`, `netflix`, `cloudflare`, `stripe`, `shopify`, `meta`, `uber`, `airbnb`, `dropbox`, `atlassian`, `slack`, `spotify`, `linkedin`, `pinterest`, `google`, `microsoft`, `etsy`, `square`, `figma`, `stackoverflow`) and specifying proposal count (1–10). |
| `/preference <text>` | `/preference focus more on technology, software architecture, and high-scale systems.` | Sets overall high-level style or topic rules for future generations. Future curations will semantically filter for topics matching this rule. |
| `/preference` | `/preference` | Displays your currently active global preference rules. |
| `/example <text>` | `/example [paste your past post text here]` | Saves one of your previous successful posts to train the AI's Few-Shot style-mimicking model. Future posts will match your tone, formatting, and spacing. |
| `/example` | `/example` | Displays a list of all your currently active writing samples, along with their unique database IDs and Type markers. |
| `/remove_example <id>` | `/remove_example 3` | Deletes a specific writing sample by its unique database ID from your style profile (use `/delete_example <id>` as an alias). |
| `/clear_examples` | `/clear_examples` | Deletes all saved past post examples from your style profile. |
| `/history` | `/history`<br>`/history approved`<br>`/history rejected`<br>`/history pending`<br>`/history skipped`<br>`/history posted`<br>`/history approved 5`<br>`/history help` | Displays proposals ordered chronologically by date descending. Accepts all statuses (`approved`, `rejected`, `pending`, `skipped`, `posted`, `all`) and an optional item limit (1–50, defaults to 10). Cards include interactive action buttons (`Show Fully`, `Refine Copy`, `Approve`, `Reject`, `Skip`, `Feedback`). |
| `/approved` | `/approved`<br>`/approved 5` | Convenience shortcut for `/history approved`. Displays recent approved posts with instant copy and graphic retrieval buttons. |

### 📰 Supported Sources (26 Channels & Blogs)

| Source Identifier | Display Name / Publication | Focus & Architecture Themes |
| :--- | :--- | :--- |
| `hn`, `hackernews` | Hacker News | Real-time tech breakthroughs, startup trends, open source. |
| `gh`, `trending` | GitHub Trending | Trending repositories across AI, infrastructure, and dev tools. |
| `arxiv`, `papers` | ArXiv Papers | Computer Science, machine learning, and agentic AI pre-prints. |
| `reddit` | Reddit Tech & ML | High-signal discussions across r/MachineLearning, r/Python, etc. |
| `lobsters` | Lobsters | Peer-curated software engineering and systems architecture. |
| `infoq` | InfoQ | Enterprise architecture, distributed systems, and modern cloud. |
| `netflix` | Netflix TechBlog | Cloud architecture, video streaming tech, and large-scale data. |
| `cloudflare`, `cf` | Cloudflare Blog | Networking, DDoS security, edge computing, and web protocols. |
| `stripe` | Stripe Engineering | API design, fintech payments, and 99.999% high-availability systems. |
| `shopify` | Shopify Engineering | E-commerce scaling, multi-tenancy, and Ruby/Go architecture. |
| `meta`, `fb` | Meta Engineering | Hyper-scale infrastructure, PyTorch, AI research, and systems. |
| `uber` | Uber Engineering | Distributed systems, logistics optimization, mobile, and Go stacks. |
| `airbnb` | Airbnb Engineering | Frontend architecture, data infrastructure, and machine learning. |
| `github_engineering` | GitHub Engineering | Git scalability, developer workflows, and enterprise platform security. |
| `dropbox` | Dropbox Tech Blog | Sync engine design, custom file storage, and kernel performance. |
| `atlassian` | Atlassian Engineering | Collaboration platforms, agile tool scaling, and Jira cloud. |
| `slack` | Slack Engineering | Real-time messaging, WebSocket protocols, and client performance. |
| `spotify` | Spotify Engineering | Audio streaming protocols, agile team scaling, and ML models. |
| `linkedin` | LinkedIn Engineering | Large-scale graph databases, recommendations, and Kafka data pipelines. |
| `pinterest` | Pinterest Engineering | Visual search algorithms, Pin serving infrastructure, and graph DBs. |
| `google`, `google_dev` | Google Developers | Web standards, Android internals, AI models, and cloud tooling. |
| `microsoft`, `msft` | Microsoft Engineering | Azure cloud internals, Windows platform, and developer tooling. |
| `etsy` | Etsy Code as Craft | Continuous delivery, engineering culture, and performance metrics. |
| `square` | Square Corner Blog | Hardware and software integration, terminal payments, and mobile security. |
| `figma` | Figma Tech Blog | WebGL internals, browser performance, and multiplayer CRDTs. |
| `stackoverflow`, `so` | Stack Overflow Engineering | Site reliability, database migrations, and community platform design. |

### 🛠️ Interactive Proposal & Copy Editing

In addition to the commands, the bot supports two conversational interactive feedback loops:

1. **Proposal Card Buttons**:
   - **`Approve 👍`**: finalizes the concept, expands into full copywriting draft, renders a custom high-res PNG card, and dispatches both sequentially.
   - **`Reject 👎`**: marks the concept rejected. The LLM remembers this as a negative constraint for future suggestions.
   - **`Skip ➡️`**: skips the item and cleans up the message card.
   - **`Feedback 💬`**: triggers a text critique prompt, allowing you to type adjustments (e.g. *"make it more technical"*) to immediately rewrite the card.
2. **`Refine Copy ✍️` Button**:
   - Delivered underneath your final expanded copywriting text. Tapping it lets you type specific edits on your phone (e.g. *"remove emojis and shorten paragraph 2"*). Llama 3.1 instantly rewrites the post and returns the updated text copy with another refinement button, allowing for infinite recursive revisions!

### 🧬 Personal Style Mimicking

The bot features a sophisticated **Few-Shot Style Profiler** to train the AI's personal branding style model:

1. **Manual Samples (The Anchor)**:
   - Paste posts you wrote manually in the past using `/example`.
   - These are cataloged in SQLite and **always take absolute precedence** in Llama's memory context to ensure your authentic human voice is never lost.
2. **Anchor Integrity (No AI Drift)**:
   - To prevent **AI Echo Drift**—where an LLM slowly starts mimicking its own generations and degrading over time—the style-mimicking model is **strictly manual-only**. Only posts you manually feed using `/example` will ever train the model's voice parameters.
3. **Specific Sample Management**:
   - View your active examples and their database IDs using `/example`.
   - Delete any specific sample from your training profile using `/remove_example <id>`.

---

## 🧪 Running the Test Suite

We maintain a 100% green test suite using `pytest` and `pytest-asyncio`. Run all tests using:
```bash
pytest
# or
python -m pytest
```
You can also run specific test modules:
```bash
# Test Curation Pipeline
python -m pytest tests/test_curator.py

# Test Database Caching
python -m pytest tests/test_database.py

# Test AI Providers
python -m pytest tests/test_llm.py

# Test Bot Core and Security Restrict Decorator
python -m pytest tests/test_bot.py

# Test Visual Card Rendering
python -m pytest tests/test_renderer.py
```
