import os
from unittest.mock import AsyncMock, Mock

import pytest

import src.config as config
import src.db.database as db
from src.bot import (
    approved_command,
    button_callback_handler,
    clear_examples_command,
    example_command,
    history_command,
    preference_command,
    remove_example_command,
    restricted,
)
from src.db.models import Proposal


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    # Use a temporary isolated database file for each test
    test_db_file = str(tmp_path / "test_bot_history.db")
    monkeypatch.setattr(db, "DATABASE_PATH", test_db_file)
    db.initialize_db()
    yield


@pytest.mark.asyncio
async def test_restricted_decorator_allowed(monkeypatch):
    # Set allowed chat id to a specific integer
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)

    # Mock update and context
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.callback_query = None

    mock_context = Mock()

    # Target function to decorate
    mock_handler = AsyncMock(return_value="success")

    decorated = restricted(mock_handler)

    result = await decorated(mock_update, mock_context)

    assert result == "success"
    mock_handler.assert_called_once_with(mock_update, mock_context)


@pytest.mark.asyncio
async def test_restricted_decorator_blocked(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)

    # Unauthorized chat ID
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=99999)
    mock_update.callback_query = None

    mock_context = Mock()

    mock_handler = AsyncMock()

    decorated = restricted(mock_handler)

    result = await decorated(mock_update, mock_context)

    # Verified: returned None (dropped silently) and inner handler was never called
    assert result is None
    mock_handler.assert_not_called()


@pytest.mark.asyncio
async def test_button_callback_handler_approve(monkeypatch, mocker):
    # Set config values
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    monkeypatch.setattr(config, "POSTS_DIR", "/tmp")

    # 1. Mock Database calls
    mock_proposal = Proposal(
        id=456,
        url="https://example.com/arxiv-v3",
        title="Example Paper",
        source="arxiv",
        summary="A paper abstract",
        proposed_title="The Future of AI Systems",
        proposed_angle="Exploring model integration strategies",
        status="pending",
    )

    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)
    mock_update_status = mocker.patch("src.db.database.update_proposal_status")
    mock_update_copy = mocker.patch("src.db.database.update_proposal_completed_copy")
    mocker.patch("src.db.database.remove_style_example_by_proposal")
    mocker.patch("src.db.database.add_style_example")
    mock_get_samples = mocker.patch("src.db.database.get_style_examples", return_value=["mock sample"])

    # 2. Mock LLM calls
    mock_provider = Mock()
    mock_provider.generate_post_text = Mock(return_value="Full expanded post text copy!")
    mock_get_provider = mocker.patch("src.bot.get_llm_provider", return_value=mock_provider)

    # 3. Mock Graphic Rendering call
    mock_render = mocker.patch("src.bot.render_graphic", new_callable=AsyncMock)

    # 4. Mock builtins open to avoid opening file on disk during send_photo
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"fake_image_bytes"))

    # 5. Mock Update & Context objects
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)

    mock_query = AsyncMock()
    mock_query.data = "approve_456"
    mock_query.message = Mock(chat_id=12345)
    mock_update.callback_query = mock_query

    mock_context = Mock()
    mock_context.bot = AsyncMock()

    # Trigger button_callback_handler (without decorator to isolate test logic)
    # Since restricted wrapper has its own tests, we test the core logic here
    from src.bot import button_callback_handler

    await button_callback_handler(mock_update, mock_context)

    # Verify DB state updates
    mock_get_prop.assert_called_once_with(456)
    mock_update_status.assert_called_once_with(456, "approved")

    # Verify LLM generation trigger
    mock_get_provider.assert_called_once()
    mock_provider.generate_post_text.assert_called_once_with(mock_proposal, style_examples=["mock sample"])

    # Verify graphic renderer triggers with appropriate mapping
    mock_render.assert_called_once_with(
        title="The Future of AI Systems",
        subtitle="Exploring model integration strategies",
        category="Arxiv",  # String mappings
        output_path=os.path.join("/tmp", "post_456.png"),
    )

    # Verify delivery back to Telegram
    assert mock_context.bot.send_message.call_count == 2

    # Message 1: Formatted Preview
    call_args_1 = mock_context.bot.send_message.call_args_list[0][1]
    assert call_args_1["chat_id"] == 12345
    assert "Formatted Preview" in call_args_1["text"]
    assert "parse_mode" not in call_args_1

    # Message 2: One-tap Copy Block with Refine button
    call_args_2 = mock_context.bot.send_message.call_args_list[1][1]
    assert call_args_2["chat_id"] == 12345
    assert "Tap the block below" in call_args_2["text"]
    assert call_args_2["parse_mode"] == "Markdown"
    assert call_args_2["reply_markup"].inline_keyboard[0][0].callback_data == "refine_copy_456"

    mock_context.bot.send_photo.assert_called_once()
    assert mock_context.bot.send_photo.call_args[1]["chat_id"] == 12345
    assert mock_context.bot.send_photo.call_args[1]["caption"] == "🎨 Generated Graphic Asset"


@pytest.mark.asyncio
async def test_button_callback_handler_refine_copy(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)

    # Mock database
    mock_proposal = Proposal(
        id=999,
        url="https://xxx.com",
        title="Title",
        source="hn",
        summary="S",
        proposed_title="Proposed Title",
        proposed_angle="Proposed Angle",
        status="approved",
    )
    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)

    # Mock Update & Query
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)

    mock_query = AsyncMock()
    mock_query.data = "refine_copy_999"
    mock_query.message = AsyncMock(chat_id=12345)
    mock_update.callback_query = mock_query

    mock_context = Mock(user_data={})
    mock_context.bot = AsyncMock()

    await button_callback_handler(mock_update, mock_context)

    # State set
    assert mock_context.user_data["waiting_for_copy_refinement_proposal_id"] == 999
    # Prompt sent
    mock_context.bot.send_message.assert_called_once()
    call_kwargs = mock_context.bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 12345
    assert "instructions to edit" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_button_callback_handler_posted(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)

    mock_proposal = Proposal(
        id=999,
        url="https://xxx.com",
        title="Title",
        source="hn",
        summary="S",
        proposed_title="Proposed Title",
        proposed_angle="Proposed Angle",
        status="approved",
    )
    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)
    mock_update_status = mocker.patch("src.db.database.update_proposal_status")

    # Mock Update & Query
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)

    mock_query = AsyncMock()
    mock_query.data = "posted_999"
    mock_query.message = AsyncMock(chat_id=12345)
    mock_update.callback_query = mock_query

    mock_context = Mock()

    await button_callback_handler(mock_update, mock_context)

    # DB state updates
    mock_get_prop.assert_called_once_with(999)
    mock_update_status.assert_called_once_with(999, "posted")

    # Message edited
    mock_query.edit_message_text.assert_called_once()
    assert "Posted!" in mock_query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_text_copy_refinement(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)

    # Mock Database
    mock_proposal = Proposal(
        id=999,
        url="https://xxx.com",
        title="Title",
        source="hn",
        summary="S",
        proposed_title="Proposed Title",
        proposed_angle="Proposed Angle",
        status="approved",
        completed_copy="Original completed copy",
    )
    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)
    mock_update_copy = mocker.patch("src.db.database.update_proposal_completed_copy")
    mocker.patch("src.db.database.remove_style_example_by_proposal")
    mocker.patch("src.db.database.add_style_example")
    mock_get_samples = mocker.patch("src.db.database.get_style_examples", return_value=["Sample writing"])

    # Mock LLM provider
    mock_provider = Mock()
    mock_provider.refine_post_text = Mock(return_value="Refined post copy text!")
    mock_get_provider = mocker.patch("src.bot.get_llm_provider", return_value=mock_provider)

    # Mock Update & Context
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()
    mock_update.message.text = "Make it shorter"

    mock_status_msg = AsyncMock()
    mock_update.message.reply_text.return_value = mock_status_msg

    mock_context = Mock()
    mock_context.user_data = {"waiting_for_copy_refinement_proposal_id": 999}

    from src.bot import handle_text_feedback

    await handle_text_feedback(mock_update, mock_context)

    # Waiting state cleared immediately
    assert "waiting_for_copy_refinement_proposal_id" not in mock_context.user_data

    # DB calls
    mock_get_prop.assert_called_once_with(999)
    mock_get_samples.assert_called_once_with(limit=3)
    mock_update_copy.assert_called_once_with(999, "Refined post copy text!")

    # LLM call
    mock_get_provider.assert_called_once()
    mock_provider.refine_post_text.assert_called_once_with(
        current_copy="Original completed copy", critique="Make it shorter", style_examples=["Sample writing"]
    )

    # Status delete
    mock_status_msg.delete.assert_called_once()

    # Reply contains Refine Copy markup in the copy block message
    assert mock_update.message.reply_text.call_count == 3

    # Message 2: Preview
    preview_reply = mock_update.message.reply_text.call_args_list[1]
    assert "REFINED LINKEDIN POST" in preview_reply[0][0]
    assert "Critique applied" in preview_reply[0][0]

    # Message 3: Copy Block with Refine button
    copy_reply = mock_update.message.reply_text.call_args_list[2]
    assert "Tap the block below" in copy_reply[0][0]
    assert "Refined post copy text!" in copy_reply[0][0]
    reply_markup = copy_reply[1]["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "refine_copy_999"


@pytest.mark.asyncio
async def test_handle_text_feedback(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    # Mock database
    mock_proposal = Proposal(
        id=456,
        url="https://test.com",
        title="Original Tech Title",
        source="hn",
        summary="A summary",
        proposed_title="Proposed social title",
        proposed_angle="Proposed social angle",
        status="pending",
    )
    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)
    mock_update_feedback = mocker.patch("src.db.database.update_proposal_feedback")
    mock_save_prop = mocker.patch("src.db.database.save_proposal")

    # Mock LLM provider
    mock_regenerated = Proposal(
        id=456,
        url="https://test.com",
        title="Original Tech Title",
        source="hn",
        summary="A summary",
        proposed_title="Refined Title",
        proposed_angle="Refined Angle",
        status="pending",
        feedback="Make it cooler",
    )
    mock_provider = Mock()
    mock_provider.regenerate_proposal = Mock(return_value=mock_regenerated)
    mock_get_provider = mocker.patch("src.bot.get_llm_provider", return_value=mock_provider)

    # Mock Update & Context
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()
    mock_update.message.text = "Make it cooler"

    # Setup status loading message mockup
    mock_status_msg = AsyncMock()
    mock_update.message.reply_text.return_value = mock_status_msg

    mock_context = Mock()
    mock_context.user_data = {"waiting_for_feedback_proposal_id": 456}

    from src.bot import handle_text_feedback

    await handle_text_feedback(mock_update, mock_context)

    # Verify state cleared immediately
    assert "waiting_for_feedback_proposal_id" not in mock_context.user_data

    # Verify DB actions
    mock_get_prop.assert_called_once_with(456)
    mock_update_feedback.assert_called_once_with(456, "Make it cooler")
    mock_save_prop.assert_called_once_with(mock_regenerated)

    # Verify LLM call
    mock_get_provider.assert_called_once()
    mock_provider.regenerate_proposal.assert_called_once_with(mock_proposal, "Make it cooler")

    # Verify status delete and final dispatch
    mock_status_msg.delete.assert_called_once()
    assert mock_update.message.reply_text.call_count == 2

    # Verify keyboard elements
    final_reply_args = mock_update.message.reply_text.call_args_list[1]
    msg_text = final_reply_args[0][0]
    reply_markup = final_reply_args[1]["reply_markup"]

    assert "Refined Title" in msg_text
    assert "Refined Angle" in msg_text
    assert "Feedback applied" in msg_text

    # Buttons count checking (4 buttons total: Approve, Reject, Skip, and Feedback)
    buttons = reply_markup.inline_keyboard
    assert len(buttons) == 2  # 2 rows
    assert len(buttons[0]) == 3  # Approve, Reject, Skip
    assert len(buttons[1]) == 1  # Feedback


@pytest.mark.asyncio
async def test_preference_command_set(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_set_pref = mocker.patch("src.db.database.set_preference")

    # Mock Update & Context
    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()
    mock_context.args = ["I", "want", "more", "focused", "on", "software"]

    await preference_command(mock_update, mock_context)

    # Verify DB setting
    mock_set_pref.assert_called_once_with("global_feedback", "I want more focused on software")

    # Verify response message
    mock_update.message.reply_text.assert_called_once()
    assert "Global Preference Saved!" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_preference_command_view(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_get_pref = mocker.patch("src.db.database.get_preference", return_value="Active global rule text")

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()
    mock_context.args = []  # Empty args to view instead of set

    await preference_command(mock_update, mock_context)

    # Verify DB getting
    mock_get_pref.assert_called_once_with("global_feedback")

    # Verify response shows current preference
    mock_update.message.reply_text.assert_called_once()
    assert "Active global rule text" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_example_command_set(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_add_sample = mocker.patch("src.db.database.add_style_example")

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()
    mock_context.args = ["This", "is", "a", "sample", "post", "content"]

    await example_command(mock_update, mock_context)

    # Verify DB call
    mock_add_sample.assert_called_once_with("This is a sample post content")

    # Verify reply
    mock_update.message.reply_text.assert_called_once()
    assert "Style Example Saved!" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_example_command_view(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_samples_detailed = [
        {"id": 1, "content": "Sample content 1", "type": "manual"},
        {"id": 2, "content": "Sample content 2", "type": "approved"},
    ]
    mock_get_samples = mocker.patch("src.db.database.get_style_examples_detailed", return_value=mock_samples_detailed)

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()
    mock_context.args = []

    await example_command(mock_update, mock_context)

    # Verify DB getting
    mock_get_samples.assert_called_once_with(limit=10)

    # Verify reply
    mock_update.message.reply_text.assert_called_once()
    msg = mock_update.message.reply_text.call_args[0][0]
    assert "Active Writing Style Samples" in msg
    assert "Sample content 1" in msg
    assert "Sample content 2" in msg
    assert "ID: 1" in msg
    assert "ID: 2" in msg


@pytest.mark.asyncio
async def test_remove_example_command(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_delete_sample = mocker.patch("src.db.database.delete_style_example", return_value=True)

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()
    mock_context.args = ["12"]

    await remove_example_command(mock_update, mock_context)

    # Verify DB call
    mock_delete_sample.assert_called_once_with(12)

    # Verify reply
    mock_update.message.reply_text.assert_called_once()
    assert "Style example ID 12 has been successfully removed" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_clear_examples_command(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_clear_samples = mocker.patch("src.db.database.clear_style_examples")

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()

    await clear_examples_command(mock_update, mock_context)

    # Verify DB clearing
    mock_clear_samples.assert_called_once()

    # Verify reply
    mock_update.message.reply_text.assert_called_once()
    assert "cleared" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_approved_command_empty(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_get_hist = mocker.patch("src.db.database.get_history", return_value=[])

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()

    await approved_command(mock_update, mock_context)

    mock_get_hist.assert_called_once_with("approved", limit=10)
    mock_update.message.reply_text.assert_called_once()
    assert "No approved posts found" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_approved_command_populated(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_prop = Proposal(
        id=777,
        url="https://xxx.com",
        title="Topology Migration",
        source="netflix_tech",
        summary="A summary",
        proposed_title="How Netflix Migrates Topologies",
        proposed_angle="Exploring scale",
        status="approved",
    )
    mock_get_hist = mocker.patch("src.db.database.get_history", return_value=[mock_prop])

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()

    await approved_command(mock_update, mock_context)

    mock_get_hist.assert_called_once_with("approved", limit=10)
    assert mock_update.message.reply_text.call_count == 2

    preview_args = mock_update.message.reply_text.call_args_list[1]
    msg = preview_args[0][0]
    reply_markup = preview_args[1]["reply_markup"]

    assert "Topology Migration" in msg
    assert "How Netflix Migrates Topologies" in msg
    assert len(reply_markup.inline_keyboard) == 3  # 3 rows of buttons now
    assert reply_markup.inline_keyboard[0][0].callback_data == "retrieve_777"
    assert reply_markup.inline_keyboard[1][0].callback_data == "posted_777"


@pytest.mark.asyncio
async def test_history_command_timeline(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    mock_prop_all = [
        Proposal(
            id=1,
            url="https://x.com",
            title="Title 1",
            source="hn",
            summary="S",
            proposed_title="PT1",
            proposed_angle="PA1",
            status="approved",
        ),
        Proposal(
            id=2,
            url="https://y.com",
            title="Title 2",
            source="gh",
            summary="S",
            proposed_title="PT2",
            proposed_angle="PA2",
            status="rejected",
            feedback="Not engineering",
        ),
        Proposal(
            id=3,
            url="https://z.com",
            title="Title 3",
            source="arxiv",
            summary="S",
            proposed_title="PT3",
            proposed_angle="PA3",
            status="skipped",
        ),
    ]
    mock_get_all_hist = mocker.patch("src.db.database.get_all_history", return_value=mock_prop_all)

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)
    mock_update.message = AsyncMock()

    mock_context = Mock()

    await history_command(mock_update, mock_context)

    mock_get_all_hist.assert_called_once_with(limit=10)
    assert mock_update.message.reply_text.call_count == 4

    # Check Welcome Message
    assert "Your Recent Proposal Timeline" in mock_update.message.reply_text.call_args_list[0][0][0]

    # Card 1 (Approved): Should have status indicator, title, and retrieval keyboard
    card1_args = mock_update.message.reply_text.call_args_list[1]
    assert "🟢 Approved" in card1_args[0][0]
    assert "Title 1" in card1_args[0][0]
    assert card1_args[1]["reply_markup"].inline_keyboard[0][0].callback_data == "retrieve_1"

    # Card 2 (Rejected): Should have status indicator, title, and standard interactive keyboard
    card2_args = mock_update.message.reply_text.call_args_list[2]
    assert "🔴 Rejected" in card2_args[0][0]
    assert "Title 2" in card2_args[0][0]
    assert "Not engineering" in card2_args[0][0]
    assert card2_args[1]["reply_markup"].inline_keyboard[0][0].callback_data == "approve_2"

    # Card 3 (Skipped): Should have status indicator, title, and standard interactive keyboard
    card3_args = mock_update.message.reply_text.call_args_list[3]
    assert "⚪ Skipped" in card3_args[0][0]
    assert "Title 3" in card3_args[0][0]
    assert card3_args[1]["reply_markup"].inline_keyboard[0][0].callback_data == "approve_3"


@pytest.mark.asyncio
async def test_button_callback_handler_retrieve(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    monkeypatch.setattr(config, "POSTS_DIR", "/tmp")

    mock_proposal = Proposal(
        id=888,
        url="https://xxx.com",
        title="Topology Migration",
        source="netflix_tech",
        summary="A summary",
        proposed_title="How Netflix Migrates Topologies",
        proposed_angle="Exploring scale",
        status="approved",
    )
    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)
    mock_update_copy = mocker.patch("src.db.database.update_proposal_completed_copy")
    mocker.patch("src.db.database.remove_style_example_by_proposal")
    mocker.patch("src.db.database.add_style_example")
    mock_get_samples = mocker.patch("src.db.database.get_style_examples", return_value=["Sample style"])

    # Mock LLM provider
    mock_provider = Mock()
    mock_provider.generate_post_text = Mock(return_value="Full expanded post text copy!")
    mock_get_provider = mocker.patch("src.bot.get_llm_provider", return_value=mock_provider)

    # Mock Graphic Rendering call
    mock_render = mocker.patch("src.bot.render_graphic", new_callable=AsyncMock)

    # Mock builtins open to avoid opening file on disk during send_photo
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"fake_image_bytes"))

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)

    mock_query = AsyncMock()
    mock_query.data = "retrieve_888"
    mock_query.message = AsyncMock(chat_id=12345)
    mock_update.callback_query = mock_query

    mock_context = Mock()
    mock_context.bot = AsyncMock()

    await button_callback_handler(mock_update, mock_context)

    mock_get_prop.assert_called_once_with(888)
    mock_get_samples.assert_called_once_with(limit=3)
    mock_update_copy.assert_called_once_with(888, "Full expanded post text copy!")
    mock_provider.generate_post_text.assert_called_once_with(mock_proposal, style_examples=["Sample style"])

    # Verify graphic renderer triggers with appropriate mapping
    mock_render.assert_called_once_with(
        title="How Netflix Migrates Topologies",
        subtitle="Exploring scale",
        category="Netflix Tech",  # String mappings
        output_path=os.path.join("/tmp", "post_888.png"),
    )

    # Verify delivery back to Telegram
    assert mock_context.bot.send_message.call_count == 2

    # Message 1: Formatted Preview
    call_args_1 = mock_context.bot.send_message.call_args_list[0][1]
    assert call_args_1["chat_id"] == 12345
    assert "Formatted Preview" in call_args_1["text"]
    assert "parse_mode" not in call_args_1

    # Message 2: One-tap Copy Block with Refine button
    call_args_2 = mock_context.bot.send_message.call_args_list[1][1]
    assert call_args_2["chat_id"] == 12345
    assert "Tap the block below" in call_args_2["text"]
    assert call_args_2["parse_mode"] == "Markdown"
    assert call_args_2["reply_markup"].inline_keyboard[0][0].callback_data == "refine_copy_888"

    mock_context.bot.send_photo.assert_called_once()
    assert mock_context.bot.send_photo.call_args[1]["chat_id"] == 12345
    assert mock_context.bot.send_photo.call_args[1]["caption"] == "🎨 Retrieved Graphic Asset"


@pytest.mark.asyncio
async def test_button_callback_handler_retrieve_cached(monkeypatch, mocker):
    monkeypatch.setattr(config, "ALLOWED_CHAT_ID", 12345)
    monkeypatch.setattr(config, "POSTS_DIR", "/tmp")

    # Proposal WITH cached completed copywriting
    mock_proposal = Proposal(
        id=888,
        url="https://xxx.com",
        title="Topology Migration",
        source="netflix_tech",
        summary="A summary",
        proposed_title="How Netflix Migrates Topologies",
        proposed_angle="Exploring scale",
        status="approved",
        completed_copy="Pre-compiled cached copy",
    )
    mock_get_prop = mocker.patch("src.db.database.get_proposal", return_value=mock_proposal)
    mock_update_copy = mocker.patch("src.db.database.update_proposal_completed_copy")
    mock_get_samples = mocker.patch("src.db.database.get_style_examples")

    # Mock LLM provider
    mock_provider = Mock()
    mock_get_provider = mocker.patch("src.bot.get_llm_provider")

    # Mock Graphic Rendering call
    mocker.patch("src.bot.render_graphic", new_callable=AsyncMock)

    # Mock builtins open to avoid opening file on disk during send_photo
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"fake_image_bytes"))

    mock_update = Mock()
    mock_update.effective_chat = Mock(id=12345)

    mock_query = AsyncMock()
    mock_query.data = "retrieve_888"
    mock_query.message = AsyncMock(chat_id=12345)
    mock_update.callback_query = mock_query

    mock_context = Mock()
    mock_context.bot = AsyncMock()

    await button_callback_handler(mock_update, mock_context)

    mock_get_prop.assert_called_once_with(888)

    # Assert LLM and style samples are NOT called because copy is pre-saved!
    mock_get_samples.assert_not_called()
    mock_get_provider.assert_not_called()
    mock_update_copy.assert_not_called()

    # Verify delivery back to Telegram contains the EXACT pre-compiled cached text!
    assert mock_context.bot.send_message.call_count == 2
    call_args_1 = mock_context.bot.send_message.call_args_list[0][1]
    assert "Pre-compiled cached copy" in call_args_1["text"]

    call_args_2 = mock_context.bot.send_message.call_args_list[1][1]
    assert "Pre-compiled cached copy" in call_args_2["text"]
