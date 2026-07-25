# AI LinkedIn Post Generator Bot 🤖

A secure, autonomous Telegram Bot that curates top tech news, generates engaging LinkedIn post drafts using Google Gemini or local Ollama models, learns from your feedback, and renders modern social graphics using Tailwind CSS and Playwright. It keeps the "human-in-the-loop" for final approvals via mobile-friendly interactive buttons.

---

## 🚀 How to Run Locally

### 1. Prerequisites
- **Python 3.10 to 3.13** installed on your system.
- A **Telegram Bot Token** (obtainable via [@BotFather](https://t.me/BotFather) on Telegram).
- Your **Telegram Chat ID** (obtainable via [@userinfobot](https://t.me/userinfobot) to restrict bot access to yourself).
- **Google Gemini API Key** (optional, required if using Gemini).
- **Ollama** installed and running locally with a model like `llama3` (optional, required if running locally).

---

### 2. Setup Instructions

#### Step A: Clone / Navigate to the Project Directory
Make sure you are in the project's root folder:
```bash
cd ai-linkedin-automation
```

#### Step B: Create and Configure your `.env` File
Copy the example environment configuration:
```bash
cp .env.example .env
```
Open the newly created `.env` file in your favorite text editor and fill in your details:
- Set `TELEGRAM_BOT_TOKEN` to your bot's token.
- Set `ALLOWED_CHAT_ID` to your personal numeric Telegram Chat ID (e.g., `123456789`).
- Set `LLM_PROVIDER` to either `gemini` or `ollama`.
- If using Gemini: set `GEMINI_API_KEY` to your Google AI Studio API key.
- If using Ollama: ensure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull llama3`).

---

### 3. Install Dependencies & Playwright Browser

Create a virtual environment, activate it, and install Python dependencies:
```bash
# Create Virtual Environment
python3 -m venv .venv

# Activate Virtual Environment (macOS/Linux)
source .venv/bin/activate

# On Windows (Command Prompt)
# .venv\Scripts\activate.bat

# Install Requirements
pip install -r requirements.txt
pip install pytest-asyncio
```

Install the headless Chromium browser binary required by Playwright for graphic rendering:
```bash
playwright install chromium
```

---

### 4. Running the Pipelines & Utilities

Our modular architecture allows you to run and test individual slices of the system directly from the command line:

#### A. Run the News Curation Agent
This script runs the daily news curation pipeline. It pulls fresh posts from Hacker News, GitHub Trending, ArXiv, and Reddit, filters out any URLs that already exist in the database, and prints a neat list of fresh items:
```bash
python -m src.curator
```

#### B. Run the Proposal Generation Agent (LLM Integration)
This runs the full proposal generation engine. It curates articles, queries your SQLite database for positive styles and negative rejections, submits them to your active LLM provider (Gemini/Ollama), and prints the 3-5 structured concepts:
```bash
python -m src.generate_proposals
```

#### C. Run the Tailwind Graphics Renderer
This tests the visual rendering engine. It loads the glassmorphic HTML template, injects mock post variables, and saves a pixel-perfect social graphic to `posts/cli_test_graphic.png`:
```bash
python -m src.renderer
```

---

### 5. Launching the Telegram Bot

To launch the primary interactive Telegram bot interface:
```bash
python -m src.bot
```

Once running:
1. Open your bot on Telegram and type `/start`. If your Telegram Chat ID matches the `ALLOWED_CHAT_ID` env variable, the bot will welcome you. (Unauthorized users are ignored silently).
2. Send the `/generate` command to kick off news curation and proposal creation.
3. Review the proposal cards sent to you and tap **Approve 👍**, **Reject 👎**, or **Skip ➡️** directly in Telegram.
4. Tapping **Approve** will automatically generate the final professional post copy and a beautiful visual graphic card, returning both assets directly to your chat for easy copy-pasting to LinkedIn!

---

## 🤖 Telegram Bot Commands

Once your Telegram Bot is live and connected, the following commands are available to help you curate, generate, train, and manage your LinkedIn post drafts:

| Command | Usage / Example | Description |
| :--- | :--- | :--- |
| `/start`, `/help` | `/help` | Initial greeting, help manual, and instructions screen listing all commands and usage. |
| `/generate` | `/generate` | Triggers a fresh technical curation from all 7 sources, queries your learning preferences history, and dispatches interactive proposal cards with inline buttons. |
| `/preference <text>` | `/preference focus more on technology, software architecture, and high-scale systems.` | Sets overall high-level style or topic rules for future generations. Future curations will semantically filter for topics matching this rule. |
| `/preference` | `/preference` | Displays your currently active global preference rules. |
| `/example <text>` | `/example [paste your past post text here]` | Saves one of your previous successful posts to train the AI's Few-Shot style-mimicking model. Future posts will match your tone, formatting, and spacing. |
| `/example` | `/example` | Displays a list of all your currently active writing samples, along with their unique database IDs and Type markers. |
| `/remove_example <id>` | `/remove_example 3` | Deletes a specific writing sample by its unique database ID from your style profile (use `/delete_example <id>` as an alias). |
| `/clear_examples` | `/clear_examples` | Deletes all saved past post examples from your style profile. |
| `/history` | `/history` | Displays your last 10 proposal decisions as a scrollable, fully interactive card board. Each card lists status (Approved, Rejected, Skipped, Pending), details, and attaches standard action buttons (`Approve`, `Reject`, `Skip`, `Feedback`) allowing you to change past decisions on the fly! |
| `/approved` | `/approved` | Displays your last 10 approved posts as interactive cards equipped with specialized action keys (`Show Fully`, `Refine Copy`, `Reject`, `Skip`) allowing you to instantly generate, edit, or re-decide from your mobile. |

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
