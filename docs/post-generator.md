# Implementation and operations

Updated 2026-10-25. This replaces the original five-phase build plan with the implemented workflow. See [the PRD](product-requirements.md) for product scope and [AGENTS.md](../AGENTS.md) for contributor guidance.

## Runtime architecture

The application runs as one Python process with Telegram long polling. `src/bot.py` validates configuration, initializes SQLite, registers command/callback/text handlers, and starts polling. `restricted` checks `ALLOWED_CHAT_ID` before protected handlers execute.

| Module | Role |
| --- | --- |
| `src/config.py` | Load `.env`, read settings, validate required credentials, create the posts directory |
| `src/curator/base.py` | Fetcher interfaces, RSS/Atom parsing, HTML-summary cleanup |
| `src/curator/sources/` | Aggregator, engineering-blog, and custom fetchers |
| `src/curator/service.py` | Sequential fetching, source selection, and URL deduplication |
| `src/curator/similarity.py` | Keyword/bigram/category similarity ranking across saved history and curated feeds |
| `src/curator/constants.py` | Source aliases, display names, feed URLs, category labels |
| `src/llm/base.py` | Abstract interface for the five generation/synthesis/refinement operations |
| `src/llm/providers/` | Gemini via `google-genai`; Ollama via the `ollama` client |
| `src/llm/prompts.py` | Task prompts, source context, history, feedback, and writing samples |
| `src/llm/copywriting.py` | Shared editorial rules applied to every prompt builder |
| `src/db/database.py` | SQLite initialization/migrations and persistence helpers |
| `src/renderer.py` | Headless Chromium screenshot of `src/templates/graphic.html` |

## Commands and actions

| Command | Purpose |
| --- | --- |
| `/start`, `/help` | Show usage |
| `/generate [source] [count]` | Request proposals; default 3, range 1–10; source aliases and comma-separated sources supported |
| `/generate help` | Show supported sources and argument forms |
| `/preference [text]` | Display or replace global proposal preferences |
| `/example [text]` | List writing samples or save a manual example |
| `/remove_example <id>`, `/delete_example <id>` | Delete one writing sample |
| `/clear_examples` | Delete all writing samples |
| `/history [status] [count]` | Browse history; default 10, range 1–50 |
| `/approved [count]` | Browse approved posts |

Proposal buttons approve (`Approve 👍`), synthesize with related articles (`Synthesize Similar 🔗`), reject, skip, or request written feedback. Saved-post controls retrieve assets, synthesize with related articles, refine copy, and mark a post as posted. Pending feedback/refinement state lives in Telegram `context.user_data`, not SQLite, and is lost on restart.

## Generation and delivery

### Curation and proposals

`/generate` loads up to five positive-history items and five rejected items plus global preferences. It fetches the selected sources (all registered sources if omitted), filters URLs, calls the provider, saves proposals, and sends review cards. Providers request JSON and parse the response; malformed responses can yield no proposals. The requested count is not a guarantee that the model will return enough valid proposals.

The registry contains six aggregators and 20 blogs. Consult `get_source_fetchers()` in `src/curator/__init__.py` and `/generate help` for the current list. Dataclasses in `src/db/models.py` normalize articles and proposals; they do not provide runtime schema validation.

### Approval and multi-article synthesis

1. Mark the proposal `approved` (unless already `posted`) and show a generation status message.
2. For single-article approval (`Approve 👍`), load up to five recent manual style examples and request full text from the provider via `generate_post_text()`.
3. For multi-article synthesis (`Synthesize Similar 🔗`), call `gather_similar_articles()` to rank up to three related articles from recent SQLite proposals and curated feeds, then request synthesized text via `generate_synthesized_post_text()`.
4. If graphics are enabled, render `POSTS_DIR/post_<id>.png` with the proposed title, angle, and source category.
5. Save `completed_copy`, then deliver a preview (including the list of combined articles when synthesized) and a copyable text block. Fall back to plain text if Markdown delivery fails.
6. If enabled, send the PNG. Update the proposal card with retrieval, synthesis, refinement, and posted-status controls.

Rendering currently precedes saving the completed copy in approval and synthesis. A rendering failure can therefore leave the proposal approved without saved text. Error handling offers retrieval or synthesis as a recovery action.

### Retrieval and refinement

Retrieval uses `completed_copy` when present; otherwise it generates and saves text. With graphics enabled, it checks for the existing PNG and renders only if missing. With graphics disabled, it skips image generation and delivery even if a PNG exists.

Refinement sends the saved text, user instructions, and manual examples to the provider, saves the result, and returns updated text controls. It does not regenerate the image. “Mark as Posted” only changes the database status.

## Copywriting behavior

`apply_copywriting_skill()` adds the shared antislop core/copywriting adaptation to proposals, proposal regeneration, final posts, and copy refinement for both providers. Rules favor concrete evidence, plain language, preserved author voice, and internal draft/audit/revise within the same model call. No extra critique request is made.

Writing samples guide style rather than supply facts about an article. Source title and summary are included in final-post and regeneration prompts; a URL alone does not prove the model read the article. Prompt guidance is not a factual or style guarantee. No local Codex skill installation is needed at runtime.

## Configuration

| Variable | Default / requirement |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Required |
| `ALLOWED_CHAT_ID` | Required integer chat ID |
| `LLM_PROVIDER` | `gemini`; supports `gemini` or `ollama` |
| `GEMINI_API_KEY` | Required for Gemini |
| `OLLAMA_HOST` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `llama3`; set to the model installed on the chosen Ollama host |
| `GENERATE_GRAPHICS` | `false`; enable with `true`, `1`, `yes`, or `on` (case-insensitive, whitespace trimmed) |
| `DATABASE_PATH` | `history.db` |
| `POSTS_DIR` | `./posts` |

The Gemini provider currently hardcodes `gemini-1.5-flash`; there is no Gemini model environment setting. This describes the code, not a claim about current service availability.

Settings load once at startup. Existing process environment values take precedence over `.env`. Stop the existing bot with `Ctrl+C` and restart from the project root:

```bash
.venv/bin/python -m src.bot
```

Do not start a second polling process for the same bot as a restart substitute. The current local setup has graphics disabled; the checked-in default is also disabled. Keep machine-specific model choices and secrets in `.env`.

## Rendering and latency

Graphics use HTML, Tailwind CSS from its CDN, Google Fonts (Plus Jakarta Sans), and Playwright Chromium. The renderer injects text into DOM elements, waits for network idle plus 100 ms, and writes a 1200×630 PNG. It does not call an image-generation model.

For optional graphics or the direct renderer test, install Chromium:

```bash
.venv/bin/python -m playwright install chromium
```

The flag is enforced by bot handlers, not by `render_graphic()` itself. Running `.venv/bin/python -m src.renderer` always attempts the rendering smoke test.

Disabling graphics removes browser work but does not remove model latency. Provider calls are synchronous and wait for a complete response, blocking the event loop while they run. Curation also fetches sequentially. The bot has no token streaming, background inference worker, or application-level inference deadline. Telegram's configured HTTP timeouts apply to Telegram requests, not Ollama/Gemini generation.

For a slow approval, first check that the process was restarted after configuration changes, then inspect the terminal logs and, for local Ollama, `ollama ps`. “Approved” alone does not mean generation or delivery has finished.

## Persistence and verification

SQLite stores proposals with unique URLs, source metadata, proposed title/angle, status, feedback, completed copy, and creation/update timestamps. Separate tables store preferences and writing examples. `initialize_db()` creates missing tables and performs basic migrations. Back up user data before schema changes; deleting the database is not a normal upgrade step.

Run checks from the project root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check
```

Tests cover the bot, curation, database, providers/prompts, and rendering. The rendering test launches a real browser; other integrations are mocked where appropriate. The last code validation for commit `8222974` passed 77 tests and Ruff lint/format checks. No separate build or static type-check target is configured.

Manual CLI entry points also exist for curation (`python -m src.curator`), proposal generation (`python -m src.generate_proposals`), and rendering (`python -m src.renderer`). These can access live services or create local artifacts; they are not substitutes for the automated suite.
