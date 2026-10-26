# Architecture and contributor guide

This repository is a single Python Telegram bot for curating articles and drafting LinkedIn posts. The components below are modules in one process, not independently deployed agents. A human reviews the drafts and publishes to LinkedIn manually.

## Documentation

- [Product requirements and current scope](docs/product-requirements.md)
- [Implementation and operations](docs/post-generator.md)
- [Setup and command examples](README.md)

## Components and data flow

```text
Telegram long polling
  -> restricted chat-ID check
  -> bot command/callback handler
       -> curation -> provider -> proposal cards
       -> approval -> provider -> saved copy -> text delivery
                              -> optional renderer -> PNG delivery
       -> synthesis -> similarity matcher (DB + feeds) -> provider -> saved copy -> text delivery
                                                                  -> optional renderer -> PNG delivery
       -> history/retrieval -> saved copy (generate if missing)
                            -> optional cached PNG (render if missing)
SQLite stores proposals, preferences, and writing examples.
```

| Component | Implementation | Responsibility |
| --- | --- | --- |
| Coordinator | `src/bot.py` | Commands, callbacks, feedback, approval, multi-article synthesis, retrieval, text/photo delivery, startup validation, long polling |
| Access check | `restricted` in `src/bot.py` | Compare chat ID with `ALLOWED_CHAT_ID`; reject unauthorized updates before work. Rejected IDs are logged locally. |
| Curation | `src/curator/` | Fetch and normalize articles, resolve source aliases, deduplicate URLs within the batch and against saved proposals, rank similar articles |
| Provider interface | `src/llm/base.py` | Proposal generation, proposal regeneration, final text, multi-article synthesized text, copy refinement |
| Provider selection | `src/llm/factory.py` | Select Gemini or Ollama using `LLM_PROVIDER` |
| Editorial guidance | `src/llm/prompts.py`, `src/llm/copywriting.py` | Supply task inputs, history, writing samples, and shared copywriting rules |
| Storage | `src/db/database.py`, `src/db/models.py` | SQLite persistence and `Article`/`Proposal` dataclasses |
| Renderer | `src/renderer.py`, `src/templates/graphic.html` | Playwright Chromium screenshot of an HTML template at 1200×630 pixels |

The source registry in `src/curator/__init__.py` contains 26 sources: six aggregators and 20 engineering blogs. Aliases, labels, and feed configuration live in `src/curator/constants.py`. This registry is the source of truth when adding or documenting sources.

## Behavioral constraints

- Graphics are optional and disabled by default. `GENERATE_GRAPHICS=false` skips both rendering and photo delivery for approval, multi-article synthesis, and retrieval, including cached images. `true`, `1`, `yes`, and `on` enable them, case-insensitively after trimming whitespace.
- Settings are loaded at import/startup through `src/config.py`. Restart the bot after changing `.env` or code. Existing process environment values take precedence over `.env`.
- `render_graphic()` itself is unconditional. The bot applies the flag; `python -m src.renderer` and the renderer integration test still render directly.
- Approval generates new single-article copy. Multi-article synthesis (`Synthesize Similar 🔗`) approves the proposal if not already posted, gathers up to three related articles from saved history and curated feeds, generates a combined post citing the sources, and saves it as `completed_copy`. Retrieval reuses `completed_copy` when available and calls the provider only if it is missing. With graphics enabled, retrieval reuses `posts/post_<id>.png` if present.
- Copy is delivered as a preview and a copyable block with a plain-text fallback. Refinement saves the revised copy. “Mark as Posted” changes local status only; it does not publish.
- Statuses are `pending`, `approved`, `rejected`, `skipped`, and `posted`. SQLite also stores feedback, completed copy, timestamps, global preferences, and manual writing examples. Initialization includes basic schema migrations; do not delete user history as a routine migration step.
- Proposal generation uses recent positive/rejected history and global preferences. Final copy, multi-article synthesis, and refinement use up to five recent manual writing examples. This is prompt conditioning, not model training.
- Both providers receive the shared runtime adaptation of antislop editorial rules for all five LLM operations. The rules require evidence and internal draft/audit/revise within the same model call. They do not guarantee factual accuracy. Local Codex skill files are not runtime dependencies.
- Provider calls and curation are synchronous inside asynchronous Telegram handlers. Slow inference or network calls can block bot responsiveness. There is no streaming progress or application-level inference deadline. Telegram HTTP timeouts do not bound LLM generation.
- Rendering uses Tailwind from a CDN and Google Fonts, so the HTML template is not fully offline or precompiled. No image-generation model is involved.

## Development and verification

Use the project virtual environment from the repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
git diff --check
```

The rendering test launches Chromium and needs installed Playwright browser binaries and permission to launch them. Dependencies are in `requirements.txt`; test and Ruff settings are in `pyproject.toml`. No separate build or type-check target is configured.

Keep `.env`, credentials, SQLite history, and generated assets private. Document public defaults in `.env.example`; do not copy local secrets into documentation. Keep this file and `docs/` aligned with changes to commands, configuration, persistence, or provider behavior.
