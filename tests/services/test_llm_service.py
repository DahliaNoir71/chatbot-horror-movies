"""Tests for LLMService.

Uses mocks to avoid loading an actual GGUF model in CI.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.llm.llm_service import LLMService


@pytest.fixture
def mock_llama():
    """Create a mock Llama model instance."""
    mock = MagicMock()

    # Mock create_completion response
    mock.create_completion.return_value = {
        "choices": [{"text": "This is a generated response."}],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
        },
    }

    # Mock create_chat_completion response
    mock.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "This is a chat response."}}],
        "usage": {
            "prompt_tokens": 30,
            "completion_tokens": 7,
            "total_tokens": 37,
        },
    }

    return mock


@pytest.fixture
def llm_service(mock_llama):
    """Create an LLMService with a pre-injected mock model."""
    service = LLMService(
        model_path="/fake/model.gguf",
        context_length=2048,
        max_tokens=256,
        temperature=0.5,
        n_gpu_layers=0,
    )
    service._llm = mock_llama
    return service


class TestLLMServiceGenerate:
    """Tests for LLMService.generate()."""

    @staticmethod
    def test_generate_returns_text(llm_service) -> None:
        """generate() returns dict with text key."""
        result = llm_service.generate("Tell me about horror movies")
        assert "text" in result
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0

    @staticmethod
    def test_generate_returns_usage(llm_service) -> None:
        """generate() returns dict with usage stats."""
        result = llm_service.generate("Test prompt")
        assert "usage" in result
        assert result["usage"]["prompt_tokens"] == 20
        assert result["usage"]["completion_tokens"] == 8

    @staticmethod
    def test_generate_passes_parameters(llm_service, mock_llama) -> None:
        """generate() passes max_tokens and temperature to the model."""
        llm_service.generate("Test", max_tokens=100, temperature=0.3)

        call_kwargs = mock_llama.create_completion.call_args
        assert call_kwargs.kwargs["max_tokens"] == 100
        assert call_kwargs.kwargs["temperature"] == pytest.approx(0.3)

    @staticmethod
    def test_generate_uses_defaults(llm_service, mock_llama) -> None:
        """generate() uses configured defaults when no overrides given."""
        llm_service.generate("Test")

        call_kwargs = mock_llama.create_completion.call_args
        assert call_kwargs.kwargs["max_tokens"] == 256
        assert call_kwargs.kwargs["temperature"] == pytest.approx(0.5)


class TestLLMServiceGenerateChat:
    """Tests for LLMService.generate_chat()."""

    @staticmethod
    def test_generate_chat_returns_text(llm_service) -> None:
        """generate_chat() returns dict with text key."""
        messages = [
            {"role": "system", "content": "You are a horror expert."},
            {"role": "user", "content": "Recommend a scary movie."},
        ]
        result = llm_service.generate_chat(messages)
        assert "text" in result
        assert isinstance(result["text"], str)

    @staticmethod
    def test_generate_chat_returns_usage(llm_service) -> None:
        """generate_chat() returns dict with usage stats."""
        messages = [{"role": "user", "content": "Hello"}]
        result = llm_service.generate_chat(messages)
        assert result["usage"]["total_tokens"] == 37

    @staticmethod
    def test_generate_chat_passes_messages(llm_service, mock_llama) -> None:
        """generate_chat() forwards the message list to the model."""
        messages = [
            {"role": "user", "content": "Test message"},
        ]
        llm_service.generate_chat(messages)

        call_args = mock_llama.create_chat_completion.call_args
        assert call_args.kwargs["messages"] == messages


class TestLLMServiceProperties:
    """Tests for LLMService properties."""

    @staticmethod
    def test_model_path_property() -> None:
        """model_path property returns the configured path."""
        service = LLMService(model_path="/my/model.gguf")
        assert service.model_path == "/my/model.gguf"

    @staticmethod
    def test_context_length_property() -> None:
        """context_length property returns the configured value."""
        service = LLMService(context_length=8192)
        assert service.context_length == 8192
