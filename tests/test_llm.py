import pytest

from src.db.models import Article, Proposal
from src.llm.base import BaseProvider
from src.llm.factory import get_llm_provider
from src.llm.prompts import build_proposal_prompt, build_regeneration_prompt
from src.llm.providers.gemini import GeminiProvider
from src.llm.providers.ollama import OllamaProvider


def test_provider_subclassing():
    # BaseProvider is an abstract class
    with pytest.raises(TypeError):
        BaseProvider()


def test_get_llm_provider_factory(monkeypatch):
    # Test factory returns GeminiProvider when configured to 'gemini'
    monkeypatch.setattr("src.config.LLM_PROVIDER", "gemini")
    monkeypatch.setattr("src.config.GEMINI_API_KEY", "fake_key")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert isinstance(provider, BaseProvider)

    # Test factory returns OllamaProvider when configured to 'ollama'
    monkeypatch.setattr("src.config.LLM_PROVIDER", "ollama")
    provider = get_llm_provider()
    assert isinstance(provider, OllamaProvider)
    assert isinstance(provider, BaseProvider)


def test_build_proposal_prompt():
    articles = [
        Article(title="T1", url="https://url1.com", source="hn", summary="S1"),
        Article(title="T2", url="https://url2.com", source="gh", summary="S2"),
    ]
    approved = [
        Proposal(
            id=1,
            url="https://ok.com",
            title="OK",
            source="hn",
            summary="S",
            proposed_title="Style Good",
            proposed_angle="Love this angle",
            status="approved",
        )
    ]
    rejected = [
        Proposal(
            id=2,
            url="https://bad.com",
            title="BAD",
            source="hn",
            summary="S",
            proposed_title="Style Bad",
            proposed_angle="Hate this style",
            status="rejected",
        )
    ]

    prompt = build_proposal_prompt(articles, approved, rejected)

    assert "https://url1.com" in prompt
    assert "https://url2.com" in prompt
    assert "Style Good" in prompt
    assert "Love this angle" in prompt
    assert "Style Bad" in prompt
    assert "Hate this style" in prompt
    assert "JSON" in prompt


def test_gemini_generate_proposals(mocker):
    # Mock the new standard google.genai Client
    mock_client_class = mocker.patch("google.genai.Client")
    mock_client = mock_client_class.return_value

    mock_response = mocker.Mock()
    mock_response.text = """
    {
      "proposals": [
        {
          "proposed_title": "AI in 2026",
          "proposed_angle": "Discussing the status of AI model capabilities.",
          "url": "https://example.com/ai"
        }
      ]
    }
    """
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="mock_key")
    articles = [Article(title="AI", url="https://example.com/ai", source="hn", summary="desc")]

    proposals = provider.generate_proposals(articles)

    assert len(proposals) == 1
    assert proposals[0].proposed_title == "AI in 2026"
    assert proposals[0].proposed_angle == "Discussing the status of AI model capabilities."
    assert proposals[0].url == "https://example.com/ai"
    assert proposals[0].source == "hn"
    assert proposals[0].status == "pending"


def test_ollama_generate_proposals(mocker):
    # Mock the ollama client library
    mock_ollama_client = mocker.patch("ollama.Client")
    mock_instance = mock_ollama_client.return_value

    mock_response = {
        "message": {
            "content": """
            {
              "proposals": [
                {
                  "proposed_title": "Local Llama 3 Setup",
                  "proposed_angle": "Why running local LLMs is changing developer workflows.",
                  "url": "https://github.com/ollama"
                }
              ]
            }
            """
        }
    }
    mock_instance.chat.return_value = mock_response

    provider = OllamaProvider(host="http://localhost:11434", model="llama3")
    articles = [
        Article(title="Ollama", url="https://github.com/ollama", source="github_trending", summary="Local running LLMs")
    ]

    proposals = provider.generate_proposals(articles)

    assert len(proposals) == 1
    assert proposals[0].proposed_title == "Local Llama 3 Setup"
    assert proposals[0].proposed_angle == "Why running local LLMs is changing developer workflows."
    assert proposals[0].url == "https://github.com/ollama"
    assert proposals[0].source == "github_trending"
    assert proposals[0].status == "pending"


def test_build_regeneration_prompt():
    prop = Proposal(
        id=123,
        url="https://test.com",
        title="Original Tech Title",
        source="hn",
        summary="A summary",
        proposed_title="Proposed social title",
        proposed_angle="Proposed social angle",
        status="pending",
    )
    prompt = build_regeneration_prompt(prop, "Make it more professional and avoid emojis")
    assert "Proposed social title" in prompt
    assert "Proposed social angle" in prompt
    assert "Make it more professional and avoid emojis" in prompt
    assert "JSON" in prompt


def test_gemini_regenerate_proposal(mocker):
    mock_client_class = mocker.patch("google.genai.Client")
    mock_client = mock_client_class.return_value

    mock_response = mocker.Mock()
    mock_response.text = """
    {
      "proposed_title": "Regenerated Gemini Title",
      "proposed_angle": "Regenerated Gemini Angle"
    }
    """
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="mock_key")
    prop = Proposal(
        id=1,
        url="https://x.com",
        title="T",
        source="hn",
        summary="S",
        proposed_title="Old Title",
        proposed_angle="Old Angle",
        status="pending",
    )

    regen = provider.regenerate_proposal(prop, "Make it cooler")

    assert regen.proposed_title == "Regenerated Gemini Title"
    assert regen.proposed_angle == "Regenerated Gemini Angle"
    assert regen.feedback == "Make it cooler"
    assert regen.status == "pending"


def test_ollama_regenerate_proposal(mocker):
    mock_ollama_client = mocker.patch("ollama.Client")
    mock_instance = mock_ollama_client.return_value

    mock_response = {
        "message": {
            "content": """
            {
              "proposed_title": "Regenerated Ollama Title",
              "proposed_angle": "Regenerated Ollama Angle"
            }
            """
        }
    }
    mock_instance.chat.return_value = mock_response

    provider = OllamaProvider(host="http://localhost:11434", model="llama3")
    prop = Proposal(
        id=2,
        url="https://y.com",
        title="T",
        source="hn",
        summary="S",
        proposed_title="Old Title",
        proposed_angle="Old Angle",
        status="pending",
    )

    regen = provider.regenerate_proposal(prop, "Remove references to Rust")

    assert regen.proposed_title == "Regenerated Ollama Title"
    assert regen.proposed_angle == "Regenerated Ollama Angle"
    assert regen.feedback == "Remove references to Rust"
    assert regen.status == "pending"
