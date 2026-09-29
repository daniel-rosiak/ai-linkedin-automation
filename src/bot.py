import os
import re
import sys
from functools import wraps
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import src.config as config
import src.db.database as db
from src.curator import (
    SOURCE_CATEGORY_MAP,
    SOURCE_DISPLAY_NAMES,
    curate_all,
    resolve_source,
)
from src.llm.factory import get_llm_provider
from src.renderer import render_graphic


# 1. Authorization Decorator
def restricted(func):
    """Decorator to restrict access only to the ALLOWED_CHAT_ID."""

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = None
        if update.effective_chat:
            chat_id = update.effective_chat.id
        elif update.callback_query and update.callback_query.message:
            chat_id = update.callback_query.message.chat_id

        if chat_id != config.ALLOWED_CHAT_ID:
            print(f"Unauthorized access blocked from chat ID: {chat_id}")
            # If the user tries to command the bot, we drop it silently as a security feature
            return

        return await func(update, context, *args, **kwargs)

    return wrapped


# 2. Start Command
@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome message with instructions."""
    welcome_text = (
        "🤖 **LinkedIn Post Generator Bot** is online!\n\n"
        "- `/generate [source] [count]` - Generate proposals on demand (e.g. `/generate shopify 2`, `/generate 5`, `/generate help`).\n"
        "- `/preference <your guidance rules here>` - Set overall high-level style/topic rules (e.g. 'focused strictly on software architecture').\n"
        "- `/preference` - View your active global preference rules.\n"
        "- `/example <paste one of your past posts here>` - Train the AI to mimic your exact personal writing tone, line-spacing, and messaging style.\n"
        "- `/example` - View your saved writing samples with their unique IDs.\n"
        "- `/remove_example <id>` - Remove a specific writing sample by its unique database ID.\n"
        "- `/clear_examples` - Reset and delete all writing samples.\n"
        "- `/history [status] [limit]` - View proposals ordered by date desc across all or specific statuses (`approved`, `rejected`, `pending`, `skipped`, `posted`, `all`).\n"
        "- `/approved [limit]` - Shortcut for `/history approved` to view approved creations and retrieve assets.\n\n"
        "Only you (the authorized user) can interact with this bot."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


# 2.5 Preference Command
@restricted
async def preference_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets or displays the global user preference feedback for curating and drafting."""
    preference_text = " ".join(context.args).strip() if context.args else ""

    if not preference_text:
        current = db.get_preference("global_feedback")
        if current:
            await update.message.reply_text(
                f"📋 **Current Global Preference:**\n"
                f"_{current}_\n\n"
                f"To update, type: `/preference <your new feedback rules here>`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "📋 No global preferences currently set.\n\n"
                "To set overall rules, type:\n"
                "`/preference I want posts strictly focused on software architecture and tech engineering`",
                parse_mode="Markdown",
            )
        return

    db.set_preference("global_feedback", preference_text)
    await update.message.reply_text(
        f"✅ **Global Preference Saved!**\n\n"
        f"Future daily curations and proposal generation cycles will adhere strictly to:\n"
        f"_{preference_text}_",
        parse_mode="Markdown",
    )


# 2.6 Style Examples Commands
@restricted
async def example_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves a past LinkedIn post example to train the personal branding style mimic model."""
    example_text = " ".join(context.args).strip() if context.args else ""

    if not example_text:
        current_samples = db.get_style_examples_detailed(limit=10)
        if current_samples:
            reply = f"📝 **Your Active Writing Style Samples ({len(current_samples)} saved):**\n\n"
            for item in current_samples:
                sample_id = item["id"]
                sample_type = "Manual Anchor" if item["type"] == "manual" else "Auto-Learned Approval"
                content = item["content"]
                preview = content[:200] + "..." if len(content) > 200 else content
                reply += f"🔹 **ID: {sample_id}** ({sample_type})\n_{preview}_\n\n"
            reply += "To add another past post example, type: `/example <paste your post text here>`\n"
            reply += "To remove a specific sample, type: `/remove_example <id>`"
            await update.message.reply_text(reply, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "📝 No personal writing examples currently set.\n\n"
                "To train the AI to mimic your tone, voice, and spacing, paste one of your previous successful posts:\n"
                "`/example <paste your post here>`",
                parse_mode="Markdown",
            )
        return

    db.add_style_example(example_text)
    await update.message.reply_text(
        "✅ **Style Example Saved!**\n\n"
        "Future post copywriting expansions will now analyze and mimic your exact tone, voice, paragraph formatting, and layout structure!",
        parse_mode="Markdown",
    )


@restricted
async def remove_example_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deletes a specific style example by its unique database ID."""
    if not context.args:
        await update.message.reply_text(
            "❌ **Please specify the ID of the style example to remove.**\n\n"
            "To view your saved examples and their IDs, type `/example`.\n"
            "Usage: `/remove_example <id>` (e.g. `/remove_example 3`)",
            parse_mode="Markdown",
        )
        return

    try:
        example_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ **Invalid ID. Please provide a numeric database ID.**")
        return

    deleted = db.delete_style_example(example_id)
    if deleted:
        await update.message.reply_text(
            f"🗑️ **Style example ID {example_id} has been successfully removed from your profile!**\n\n"
            f"Future copywriting generations will no longer utilize this sample.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ **Style example ID {example_id} not found in database.**\n"
            f"Type `/example` to see your active samples and their valid IDs."
        )


@restricted
async def clear_examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears all saved past style examples."""
    db.clear_style_examples()
    await update.message.reply_text("🧹 **All personal writing style examples have been cleared.**")


# 2.7 History Command
VALID_HISTORY_STATUSES = {
    "all": "all",
    "approved": "approved",
    "approve": "approved",
    "rejected": "rejected",
    "reject": "rejected",
    "pending": "pending",
    "skipped": "skipped",
    "skip": "skipped",
    "posted": "posted",
    "post": "posted",
}

STATUS_DISPLAY_TITLES = {
    "approved": "Approved Posts",
    "rejected": "Rejected Proposals",
    "pending": "Pending Proposals",
    "skipped": "Skipped Proposals",
    "posted": "Posted Items",
    "all": "Proposal Timeline",
}


def parse_history_args(args: list[str]) -> tuple[Optional[str], int, Optional[str]]:
    """
    Parses arguments for /history command.
    Accepts status (approved, rejected, pending, skipped, posted, all) and/or item count limit (1-50).
    Returns (status, limit, error_or_action_str).
    """
    if not args:
        return None, 10, None

    if any(a.lower() in ("help", "--help", "-h", "statuses", "list") for a in args):
        return None, 0, "HELP"

    raw_tokens = []
    limit = 10

    i = 0
    while i < len(args):
        arg = args[i].strip()
        lower = arg.lower()
        if lower in ("--limit", "-l", "-n", "--count", "-c") and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
                i += 2
                continue
            except ValueError:
                return None, 0, f"Invalid number for limit: `{args[i + 1]}`"
        elif lower.startswith("limit=") or lower.startswith("count="):
            try:
                limit = int(arg.split("=", 1)[1])
                i += 1
                continue
            except ValueError:
                return None, 0, f"Invalid number for limit: `{arg}`"
        elif lower in ("--status", "-s") and i + 1 < len(args):
            raw_tokens.append(args[i + 1])
            i += 2
            continue
        elif lower.startswith("status="):
            raw_tokens.append(arg.split("=", 1)[1])
            i += 1
            continue
        else:
            raw_tokens.append(arg)
            i += 1

    status = None
    for token in raw_tokens:
        clean = token.strip().lower().lstrip("/")
        if clean.isdigit():
            limit = int(clean)
        elif clean.startswith("-") and clean[1:].isdigit():
            return None, 0, "Limit must be between 1 and 50."
        else:
            if clean in VALID_HISTORY_STATUSES:
                resolved = VALID_HISTORY_STATUSES[clean]
                status = None if resolved == "all" else resolved
            else:
                return None, 0, f"Unknown status `{token}`."

    if limit < 1 or limit > 50:
        return None, 0, "Limit must be between 1 and 50."

    return status, limit, None


def format_history_help() -> str:
    """Builds a formatted guide explaining /history status arguments and options."""
    return (
        "📖 **/history Command Options**\n\n"
        "View proposals ordered chronologically by date descending across all or filtered statuses:\n\n"
        "**Usage:**\n"
        "• `/history` — View last 10 proposals across all statuses\n"
        "• `/history approved` — View approved posts (also `/history approved 5`)\n"
        "• `/history rejected` — View rejected proposals\n"
        "• `/history pending` — View pending proposals\n"
        "• `/history skipped` — View skipped proposals\n"
        "• `/history posted` — View published posts\n"
        "• `/history all` — View across all statuses\n"
        "• `/history <count>` — e.g. `/history 20` (1–50 items)\n\n"
        "💡 *You can also specify both status and count: e.g. `/history approved 5`.*"
    )


@restricted
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists recent proposals across all or filtered statuses, presenting each as a fully interactive card board."""
    raw_args = context.args if isinstance(getattr(context, "args", None), list) else []
    status, limit, err = parse_history_args(raw_args)

    if err == "HELP":
        await update.message.reply_text(format_history_help(), parse_mode="Markdown")
        return

    if err:
        msg = f"⚠️ {err}\n\nType `/history help` to view all available statuses and usage options."
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    db.initialize_db()
    if status is not None:
        history = db.get_all_history(limit=limit, status=status)
    else:
        history = db.get_all_history(limit=limit)

    if not history:
        if status:
            empty_msg = (
                f"📚 **No {status} proposals found yet.**\n\n"
                "Run `/generate` to curate articles and make decisions!"
            )
        else:
            empty_msg = (
                "📚 **Your Proposal History is empty.**\n\n"
                "Run `/generate` to curate articles and make decisions. Approved, rejected, and skipped items will appear in your timeline!"
            )
        await update.message.reply_text(empty_msg, parse_mode="Markdown")
        return

    title_part = STATUS_DISPLAY_TITLES.get(status, "Proposal Timeline") if status else "Proposal Timeline"
    await update.message.reply_text(f"📚 **Your Recent {title_part} (Last {len(history)} items - ordered by date):**")

    status_emojis = {
        "approved": "🟢 Approved",
        "rejected": "🔴 Rejected",
        "skipped": "⚪ Skipped",
        "pending": "⏳ Pending",
        "posted": "🚀 Posted",
    }

    for item in history:
        status_label = status_emojis.get(item.status.lower(), item.status.upper())
        date_str = item.created_at.strftime("%m-%d %H:%M") if item.created_at else "Recent"

        msg_text = (
            f"**{status_label}** | _{date_str}_\n\n"
            f"📰 **[{item.source.upper()}] {item.title}**\n"
            f"🔗 [Original Link]({item.url})\n\n"
            f"💡 **Proposed LinkedIn Title:**\n`{item.proposed_title}`\n\n"
            f"📣 **Proposed Concept / Angle:**\n_{item.proposed_angle}_"
        )
        if item.feedback:
            msg_text += f"\n\n💬 *Feedback: '{item.feedback}'*"

        # Attach appropriate keyboard markup based on status
        status_lower = item.status.lower()
        if status_lower == "approved":
            keyboard = [
                [
                    InlineKeyboardButton("Show Fully 📥", callback_data=f"retrieve_{item.id}"),
                    InlineKeyboardButton("Refine Copy ✍️", callback_data=f"refine_copy_{item.id}"),
                ],
                [InlineKeyboardButton("Mark as Posted 🚀", callback_data=f"posted_{item.id}")],
                [
                    InlineKeyboardButton("Reject 👎", callback_data=f"reject_{item.id}"),
                    InlineKeyboardButton("Skip ➡️", callback_data=f"skip_{item.id}"),
                ],
            ]
        elif status_lower == "posted":
            keyboard = [[InlineKeyboardButton("Show Fully 📥", callback_data=f"retrieve_{item.id}")]]
        elif status_lower == "rejected":
            keyboard = [
                [
                    InlineKeyboardButton("Approve 👍", callback_data=f"approve_{item.id}"),
                    InlineKeyboardButton("Skip ➡️", callback_data=f"skip_{item.id}"),
                ]
            ]
        elif status_lower == "skipped":
            keyboard = [
                [
                    InlineKeyboardButton("Approve 👍", callback_data=f"approve_{item.id}"),
                    InlineKeyboardButton("Reject 👎", callback_data=f"reject_{item.id}"),
                ]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("Approve 👍", callback_data=f"approve_{item.id}"),
                    InlineKeyboardButton("Reject 👎", callback_data=f"reject_{item.id}"),
                    InlineKeyboardButton("Skip ➡️", callback_data=f"skip_{item.id}"),
                ],
                [InlineKeyboardButton("Feedback 💬", callback_data=f"feedback_{item.id}")],
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            msg_text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True
        )


# 2.8 Approved Command
@restricted
async def approved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists recent approved posts as interactive cards, allowing asset retrieval, edits, or re-decisions."""
    limit = 10
    args = getattr(context, "args", None)
    if isinstance(args, list) and args and args[0].isdigit():
        limit = min(max(1, int(args[0])), 50)
    approved = db.get_history("approved", limit=limit)

    if not approved:
        await update.message.reply_text(
            "📚 **No approved posts found yet.**\n\n"
            "Once you approve a generated proposal card, it will be cataloged here for immediate retrieval or copy pasting at any time!",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("📚 **Your Recent Approved Posts (Fully Interactive):**")

    for item in approved:
        keyboard = [
            [
                InlineKeyboardButton("Show Fully 📥", callback_data=f"retrieve_{item.id}"),
                InlineKeyboardButton("Refine Copy ✍️", callback_data=f"refine_copy_{item.id}"),
            ],
            [InlineKeyboardButton("Mark as Posted 🚀", callback_data=f"posted_{item.id}")],
            [
                InlineKeyboardButton("Reject 👎", callback_data=f"reject_{item.id}"),
                InlineKeyboardButton("Skip ➡️", callback_data=f"skip_{item.id}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg_text = (
            f"🟢 **Approved Post**\n\n"
            f"📰 **[{item.source.upper()}] {item.title}**\n"
            f"🔗 [Original Link]({item.url})\n\n"
            f"💡 **Proposed LinkedIn Title:**\n`{item.proposed_title}`\n\n"
            f"📣 **Proposed Concept / Angle:**\n_{item.proposed_angle}_"
        )
        if item.feedback:
            msg_text += f"\n\n💬 *Feedback: '{item.feedback}'*"

        await update.message.reply_text(
            msg_text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True
        )


def parse_generate_args(args: list[str]):
    """
    Parses arguments for /generate command.
    Returns (sources_list, count, error_or_action_str).
    If error_or_action_str is 'HELP', caller should display help.
    If error_or_action_str is another string, caller should display error.
    """
    if not args:
        return None, 3, None

    # Check for help command or flag
    if any(a.lower() in ("help", "--help", "-h", "sources", "list") for a in args):
        return None, 0, "HELP"

    raw_tokens = []
    count = 3

    i = 0
    while i < len(args):
        arg = args[i].strip()
        lower = arg.lower()
        if lower in ("--count", "-c", "-n") and i + 1 < len(args):
            try:
                count = int(args[i + 1])
                i += 2
                continue
            except ValueError:
                return None, 0, f"Invalid number for count: `{args[i + 1]}`"
        elif lower.startswith("count="):
            try:
                count = int(arg.split("=", 1)[1])
                i += 1
                continue
            except ValueError:
                return None, 0, f"Invalid number for count: `{arg}`"
        elif lower in ("--source", "-s") and i + 1 < len(args):
            raw_tokens.extend(args[i + 1].split(","))
            i += 2
            continue
        elif lower.startswith("source="):
            raw_tokens.extend(arg.split("=", 1)[1].split(","))
            i += 1
            continue
        else:
            raw_tokens.append(arg)
            i += 1

    remaining_tokens = []
    for token in raw_tokens:
        if token.isdigit():
            count = int(token)
        elif token.startswith("-") and token[1:].isdigit():
            return None, 0, "Number of items must be between 1 and 10."
        else:
            remaining_tokens.append(token)

    if count < 1 or count > 10:
        return None, 0, "Number of items must be between 1 and 10."

    if not remaining_tokens:
        return None, count, None

    sources = []
    combined = " ".join(remaining_tokens)
    parts = [p.strip() for p in combined.split(",") if p.strip()]
    for p in parts:
        resolved = resolve_source(p)
        if not resolved:
            subparts = p.split()
            sub_resolved = [resolve_source(sp) for sp in subparts if resolve_source(sp)]
            if sub_resolved:
                for sr in sub_resolved:
                    if sr not in sources:
                        sources.append(sr)
                continue
            return None, 0, f"Unknown source `{p}`."
        if resolved not in sources:
            sources.append(resolved)

    return sources, count, None


def format_generate_help() -> str:
    """Builds a formatted guide explaining how to target sources and specify counts."""
    sources_text = "\n".join(
        f"• `{key}` — {label}" for key, label in SOURCE_DISPLAY_NAMES.items()
    )
    return (
        "📖 **/generate Command Options**\n\n"
        "Generate post proposals targeting specific sources and/or specify the number of items:\n\n"
        "**Usage:**\n"
        "• `/generate` — Curates from all sources (3 proposals by default)\n"
        "• `/generate <count>` — e.g. `/generate 5` (1–10 items)\n"
        "• `/generate <source>` — e.g. `/generate shopify`\n"
        "• `/generate <source> <count>` — e.g. `/generate shopify 2` or `/generate 2 shopify`\n"
        "• `/generate <source1,source2> <count>` — e.g. `/generate netflix,shopify 4`\n"
        "• `/generate --source shopify --count 2`\n\n"
        f"**Available Sources:**\n{sources_text}\n\n"
        "💡 *Aliases supported:* `hn`, `gh`, `papers`, `netflix`, `shopify`, `cloudflare`, `stripe`, `meta`, `uber`, `airbnb`, `slack`, `spotify`, etc."
    )


# 3. Generate proposals command
@restricted
async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Curates tech news and uses LLM to generate post proposals with inline buttons."""
    sources, count, err = parse_generate_args(context.args or [])

    if err == "HELP":
        await update.message.reply_text(format_generate_help(), parse_mode="Markdown")
        return

    if err:
        msg = f"⚠️ {err}\n\nType `/generate help` to see available sources and usage options."
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if sources:
        names = [SOURCE_DISPLAY_NAMES.get(s, s) for s in sources]
        status_text = f"🔍 Curating fresh articles from {', '.join(names)} ({count} items)..."
    else:
        status_text = f"🔍 Curating tech news and engineering blogs ({count} items)..."

    status_msg = await update.message.reply_text(status_text)

    try:
        # Step 1: Initialize DB & Load histories
        db.initialize_db()
        approved_history = db.get_positive_history(limit=5)
        rejected_history = db.get_history("rejected", limit=5)
        global_feedback = db.get_preference("global_feedback")

        # Step 2: Run Curation
        limit_per_source = max(4, count * 2) if sources else max(2, (count + 7) // 8 + 1)
        articles = curate_all(limit_per_source=limit_per_source, sources=sources)
        if not articles:
            source_suffix = f" from {', '.join(names)}" if sources else " for today"
            await status_msg.edit_text(
                f"✅ All curated articles{source_suffix} have already been processed and presented! Try again later."
            )
            return

        await status_msg.edit_text(f"🤖 Initializing LLM provider and generating {count} proposals...")

        # Step 3: Call LLM Factory
        provider = get_llm_provider()
        proposals = provider.generate_proposals(
            articles=articles,
            approved_history=approved_history,
            rejected_history=rejected_history,
            global_feedback=global_feedback,
            count=count,
        )

        if not proposals:
            await status_msg.edit_text("⚠️ No proposals could be generated by the LLM today. Try again later.")
            return

        await status_msg.delete()

        # Step 4: Save & Dispatch Proposals
        for p in proposals:
            # Save to SQLite to get database assigned ID
            p.id = db.save_proposal(p)

            # Format text for proposal message
            msg_text = (
                f"📰 **[{p.source.upper()}] {p.title}**\n"
                f"🔗 [Original Link]({p.url})\n\n"
                f"💡 **Proposed LinkedIn Title:**\n`{p.proposed_title}`\n\n"
                f"📣 **Proposed Concept / Angle:**\n_{p.proposed_angle}_"
            )

            # Create interactive keyboard buttons
            keyboard = [
                [
                    InlineKeyboardButton("Approve 👍", callback_data=f"approve_{p.id}"),
                    InlineKeyboardButton("Reject 👎", callback_data=f"reject_{p.id}"),
                    InlineKeyboardButton("Skip ➡️", callback_data=f"skip_{p.id}"),
                ],
                [InlineKeyboardButton("Feedback 💬", callback_data=f"feedback_{p.id}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                msg_text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True
            )

    except Exception as e:
        print(f"Error in /generate execution: {e}")
        await status_msg.edit_text(f"❌ An error occurred during curation/generation: {e}")


# 4. Interactive Keyboard Handlers
@restricted
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes clicks on Approve, Reject, and Skip keyboard buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data
    match = re.match(r"^(approve|reject|skip|feedback|retrieve|refine_copy|posted)_(\d+)$", data)
    if not match:
        return

    action, prop_id_str = match.groups()
    proposal_id = int(prop_id_str)

    proposal = db.get_proposal(proposal_id)
    if not proposal:
        await query.edit_message_text("⚠️ Error: Proposal not found in the database.")
        return

    if action == "reject":
        db.update_proposal_status(proposal_id, "rejected")
        await query.edit_message_text(
            f"🔴 **Rejected**\nOriginal article: {proposal.title}\nAI will use this rejection to refine future posts."
        )
    elif action == "skip":
        db.update_proposal_status(proposal_id, "skipped")
        await query.edit_message_text(f"⚪ **Skipped**\nOriginal article: {proposal.title}")
    elif action == "posted":
        db.update_proposal_status(proposal_id, "posted")
        await query.edit_message_text(
            f"🚀 **Posted!**\n\n"
            f"Title: `{proposal.proposed_title}`\n\n"
            f"This post has been marked as published on LinkedIn and cataloged in your timeline!"
        )
    elif action == "feedback":
        context.user_data["waiting_for_feedback_proposal_id"] = proposal_id
        await query.edit_message_text(
            f"📰 **[{proposal.source.upper()}] {proposal.title}**\n\n"
            f"💡 **Current Title:** `{proposal.proposed_title}`\n\n"
            f"💬 Please type and send your specific written feedback/critique for this proposal:\n"
            f"_(e.g., 'Make it more technical', 'Avoid emojis', 'Focus on compilation speeds')_"
        )
    elif action == "refine_copy":
        context.user_data["waiting_for_copy_refinement_proposal_id"] = proposal_id
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "💬 Please type and send your specific instructions to edit and refine this copywriting:\n"
                "_(e.g., 'Make the second paragraph shorter', 'Remove all emojis', 'Format as bullet points')_"
            ),
        )
    elif action == "retrieve":
        status_msg = await query.message.reply_text(f"⏳ Retrieving assets for `{proposal.proposed_title}`...")
        try:
            # 1. Retrieve the copywriting text (Check DB first to prevent redundant LLM generations)
            if proposal.completed_copy:
                post_text = proposal.completed_copy
            else:
                style_examples = db.get_style_examples(limit=5)
                provider = get_llm_provider()
                post_text = provider.generate_post_text(proposal, style_examples=style_examples)
                # Save the newly generated text copy inside DB for subsequent fast retrievals
                db.update_proposal_completed_copy(proposal_id, post_text)

            category_str = SOURCE_CATEGORY_MAP.get(proposal.source.lower(), proposal.source.replace("_", " ").title())

            image_filename = f"post_{proposal_id}.png"
            image_path = os.path.join(config.POSTS_DIR, image_filename)

            await render_graphic(
                title=proposal.proposed_title,
                subtitle=proposal.proposed_angle,
                category=category_str,
                output_path=image_path,
            )

            await status_msg.delete()

            # 1. Send beautiful formatted preview (No parse_mode to prevent unescaped Markdown parsing crashes)
            await context.bot.send_message(
                chat_id=query.message.chat_id, text=f"📝 **Formatted Preview:**\n\n{post_text}"
            )

            # 2. Send one-tap copy block message with Refine Copy & Mark as Posted buttons
            copy_msg = f"📋 **Tap the block below to copy your LinkedIn post in one click:**\n\n```\n{post_text}\n```"
            keyboard = [
                [
                    InlineKeyboardButton("Refine Copy ✍️", callback_data=f"refine_copy_{proposal_id}"),
                    InlineKeyboardButton("Mark as Posted 🚀", callback_data=f"posted_{proposal_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=query.message.chat_id, text=copy_msg, parse_mode="Markdown", reply_markup=reply_markup
            )

            with open(image_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id, photo=f, caption="🎨 Retrieved Graphic Asset"
                )
        except Exception as e:
            print(f"Error in post retrieval process: {e}")
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Error during asset retrieval: {e}")
    elif action == "approve":
        db.update_proposal_status(proposal_id, "approved")
        await query.edit_message_text(
            f"🟢 **Approved!**\n"
            f"Title: `{proposal.proposed_title}`\n\n"
            f"⏳ Generating draft copywriting and social graphics assets..."
        )

        try:
            # 1. Load personal style samples (up to 5 freshest)
            style_examples = db.get_style_examples(limit=5)

            # 2. Instantiate provider & generate copywriting
            provider = get_llm_provider()
            post_text = provider.generate_post_text(proposal, style_examples=style_examples)

            # 3. Map category string beautifully
            category_str = SOURCE_CATEGORY_MAP.get(proposal.source.lower(), proposal.source.replace("_", " ").title())

            # 3. Create rendering destination path
            image_filename = f"post_{proposal_id}.png"
            image_path = os.path.join(config.POSTS_DIR, image_filename)

            # 4. Invoke Phase 4 Playwright render graphic
            await render_graphic(
                title=proposal.proposed_title,
                subtitle=proposal.proposed_angle,
                category=category_str,
                output_path=image_path,
            )

            # Save completed copywriting text copy inside DB
            db.update_proposal_completed_copy(proposal_id, post_text)

            # 1. Send beautiful formatted preview (No parse_mode to prevent unescaped Markdown parsing crashes)
            await context.bot.send_message(
                chat_id=query.message.chat_id, text=f"📝 **Formatted Preview:**\n\n{post_text}"
            )

            # 2. Send one-tap copy block message with Refine Copy & Mark as Posted buttons
            copy_msg = f"📋 **Tap the block below to copy your LinkedIn post in one click:**\n\n```\n{post_text}\n```"
            keyboard = [
                [
                    InlineKeyboardButton("Refine Copy ✍️", callback_data=f"refine_copy_{proposal_id}"),
                    InlineKeyboardButton("Mark as Posted 🚀", callback_data=f"posted_{proposal_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=query.message.chat_id, text=copy_msg, parse_mode="Markdown", reply_markup=reply_markup
            )

            # 6. Send rendered PNG graphic to the user
            with open(image_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id, photo=f, caption="🎨 Generated Graphic Asset"
                )

        except Exception as e:
            print(f"Error in post-approval delivery process: {e}")
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Error during asset delivery: {e}")


@restricted
async def handle_text_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes written text critiques and triggers AI proposal or copywriting regeneration."""
    feedback_text = update.message.text.strip()
    if not feedback_text:
        return

    # Case 1: Checking copy refinement waiting state
    refinement_id = context.user_data.get("waiting_for_copy_refinement_proposal_id")
    if refinement_id:
        context.user_data.pop("waiting_for_copy_refinement_proposal_id", None)

        proposal = db.get_proposal(refinement_id)
        if not proposal:
            await update.message.reply_text("❌ Error: Active proposal not found in database.")
            return

        status_msg = await update.message.reply_text(
            f"⏳ **Refinement received:** '{feedback_text}'\n🤖 Refining copywriting using local AI..."
        )
        try:
            style_examples = db.get_style_examples(limit=5)
            current_copy = proposal.completed_copy or ""

            provider = get_llm_provider()
            refined_text = provider.refine_post_text(
                current_copy=current_copy, critique=feedback_text, style_examples=style_examples
            )

            # Save the new refined text copy inside DB
            db.update_proposal_completed_copy(refinement_id, refined_text)

            await status_msg.delete()

            # 1. Send beautiful formatted refined preview (No parse_mode to prevent unescaped Markdown parsing crashes)
            await update.message.reply_text(
                f"🔄 **REFINED LINKEDIN POST (Preview)**\n\n{refined_text}\n\n💬 *Critique applied: '{feedback_text}'*"
            )

            # 2. Send one-tap copy block message with Refine Copy & Mark as Posted buttons
            copy_msg = f"📋 **Tap the block below to copy your refined post in one click:**\n\n```\n{refined_text}\n```"
            keyboard = [
                [
                    InlineKeyboardButton("Refine Copy ✍️", callback_data=f"refine_copy_{refinement_id}"),
                    InlineKeyboardButton("Mark as Posted 🚀", callback_data=f"posted_{refinement_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(copy_msg, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            print(f"Error during copywriting refinement: {e}")
            await status_msg.edit_text(f"❌ Failed to refine copywriting: {e}")
        return

    # Case 2: Checking standard card proposal waiting state
    proposal_id = context.user_data.get("waiting_for_feedback_proposal_id")
    if not proposal_id:
        return

    proposal = db.get_proposal(proposal_id)
    if not proposal:
        await update.message.reply_text("❌ Error: Active proposal not found in database.")
        context.user_data.pop("waiting_for_feedback_proposal_id", None)
        return

    # Clear state immediately to prevent race triggers
    context.user_data.pop("waiting_for_feedback_proposal_id", None)

    status_msg = await update.message.reply_text(
        f"⏳ **Critique received:** '{feedback_text}'\n🤖 Rewriting proposal using local AI..."
    )

    try:
        # Save feedback critique in SQLite
        db.update_proposal_feedback(proposal_id, feedback_text)

        # Instantiate provider & regenerate proposal
        provider = get_llm_provider()
        regenerated = provider.regenerate_proposal(proposal, feedback_text)

        # Save updated proposal fields back to SQLite (set status back to pending)
        db.save_proposal(regenerated)

        await status_msg.delete()

        # Dispatch the fresh card back to user for another round of reviews
        msg_text = (
            f"🔄 **REWRITTEN PROPOSAL (Feedback Incorporated)**\n\n"
            f"📰 **[{regenerated.source.upper()}] {regenerated.title}**\n"
            f"🔗 [Original Link]({regenerated.url})\n\n"
            f"💡 **New Proposed Title:**\n`{regenerated.proposed_title}`\n\n"
            f"📣 **New Concept / Angle:**\n_{regenerated.proposed_angle}_\n\n"
            f"💬 *Feedback applied: '{feedback_text}'*"
        )

        keyboard = [
            [
                InlineKeyboardButton("Approve 👍", callback_data=f"approve_{proposal_id}"),
                InlineKeyboardButton("Reject 👎", callback_data=f"reject_{proposal_id}"),
                InlineKeyboardButton("Skip ➡️", callback_data=f"skip_{proposal_id}"),
            ],
            [InlineKeyboardButton("Feedback 💬", callback_data=f"feedback_{proposal_id}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            msg_text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Error during proposal regeneration: {e}")
        await status_msg.edit_text(f"❌ Failed to rewrite proposal: {e}")


# 5. Boot / Polling
def main():
    errors = config.validate_config()
    if errors:
        print("Configuration validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("Starting Telegram Bot long-polling...")
    db.initialize_db()

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Register Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CommandHandler("preference", preference_command))
    application.add_handler(CommandHandler("example", example_command))
    application.add_handler(CommandHandler("remove_example", remove_example_command))
    application.add_handler(CommandHandler("delete_example", remove_example_command))
    application.add_handler(CommandHandler("clear_examples", clear_examples_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("approved", approved_command))

    # Register Keyboard Buttons
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # Register Custom Written Feedback Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_feedback))

    application.run_polling()


if __name__ == "__main__":
    main()
