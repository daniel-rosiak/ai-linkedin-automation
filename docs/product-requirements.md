# AI LinkedIn Post Generator: product requirements

Updated against the implementation on 2026-10-25. This document describes current scope; [the implementation guide](post-generator.md) covers code paths and operations.

## Problem and solution

Technical professionals need help finding relevant articles and drafting posts without losing editorial control. A single-owner Telegram bot curates engineering news, proposes angles, and generates drafts after approval. The user reviews and publishes manually on LinkedIn. An accompanying template graphic is optional and disabled by default.

## Current user workflow

1. Run `/generate [source] [count]`. The default request is three proposals across available sources; supported counts are 1–10. `/generate help` lists sources and syntax.
2. Review article links, proposed titles, and angles. Approve, reject, skip, or supply written feedback to regenerate a proposal.
3. Approval marks the proposal approved, requests final copy from the configured provider, saves it, and sends a preview plus a copyable block.
4. If `GENERATE_GRAPHICS=true`, approval also renders and sends a 1200×630 PNG. With the default `false`, it sends text only.
5. Refine the copy through written instructions, retrieve saved posts from history, and mark a post as published after manually posting it.

## Implemented requirements

| Area | Behavior |
| --- | --- |
| Curation | 26 registered sources: Hacker News, GitHub Trending, ArXiv, Reddit, Lobsters, InfoQ, and 20 engineering blogs. Source aliases and selection are supported. |
| Deduplication | Exclude repeated URLs within a batch and URLs already saved as proposals. Fetched articles that were not saved as proposals are not permanently marked seen. |
| Provider choice | `LLM_PROVIDER` selects Gemini or Ollama. Ollama host/model are configurable. Local inference still uses external services for Telegram, feeds, and optional rendering resources. |
| Editorial guidance | Shared rules cover factual support, author voice, natural phrasing, and internal revision in the existing model call for proposals, regeneration, final copy, and refinement. |
| Preferences | Positive and rejected history plus `/preference` guide proposal generation. Up to five recent manual `/example` samples guide final copy and refinement. No model fine-tuning occurs. |
| Retrieval | Reuse saved completed copy; generate only if missing. When graphics are enabled, reuse an existing PNG or render a missing one. When disabled, do not send cached images. |
| History | Browse all proposals or filter by pending, approved, rejected, skipped, or posted status. `/approved` is a shortcut. |
| Access | Command, callback, and free-text handlers check `ALLOWED_CHAT_ID` before performing work. Unauthorized requests receive no bot reply; their chat IDs are logged locally. |
| Storage | SQLite persists proposals, statuses, feedback, completed copy, timestamps, preferences, and writing samples. Startup includes basic schema migrations. |
| Publishing | “Mark as Posted” records local status only. No LinkedIn authentication or publishing API is used. |

## Configuration and acceptance expectations

- `GENERATE_GRAPHICS` defaults to `false`. `.env.example` documents that default. Restart the bot after changing environment settings or code.
- Text-only approval and retrieval must not render, open, or send a PNG. Text preview, copy controls, refinement, and status handling remain available.
- Enabling graphics must retain the existing Playwright path. Chromium must be installed; the template loads Tailwind CSS and Google Fonts over the network.
- Both Gemini and Ollama must receive the shared copywriting guidance through the prompt builders. Source titles and summaries accompany final-copy and proposal-regeneration prompts.
- Editorial instructions are guidance, not automated fact-checking. Writing samples may override default style restrictions, but not factual accuracy or required response formats. Human review remains required.

## Current limitations and exclusions

- Curation and provider calls are synchronous inside bot handlers. Long model calls can delay other bot interactions; there is no streaming output or application-level inference deadline. No generation-time guarantee is made.
- An approval can be recorded before text or image delivery succeeds. Retrieval provides a recovery path; if copy was not saved, it will need generation again.
- No automatic scheduled curation, direct LinkedIn posting, multi-user profiles, or deployment infrastructure is implemented.
- The project uses basic SQLite migrations, not a dedicated migration framework. Preserve existing history during upgrades.
- The test suite exercises mocked provider/Telegram behavior and a real browser rendering test. It does not establish live provider availability or factual quality of generated posts.
