"""Tests for AI settings module.

Covers: LLMSettings, ClassifierSettings, EmbeddingSettings
"""

from pathlib import Path

import pytest
from pytest import approx
from pydantic import ValidationError

from src.settings.ai import ClassifierSettings, EmbeddingSettings, LLMSettings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all AI-related environment variables for isolated testing."""
    env_vars = [
        "LLM_MODEL_PATH",
        "LLM_CONTEXT_LENGTH",
        "LLM_MAX_TOKENS",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT_SECONDS",
        "LLM_N_GPU_LAYERS",
        "CLASSIFIER_MODEL_NAME",
        "CLASSIFIER_CONFIDENCE_THRESHOLD",
        "CLASSIFIER_DEVICE",
        "EMBEDDING_MODEL_NAME",
        "EMBEDDING_DIMENSIONS",
        "EMBEDDING_BATCH_SIZE",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


# =============================================================================
# LLM SETTINGS
# =============================================================================


@pytest.fixture
def llm_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required LLM environment variables."""
    monkeypatch.setenv("LLM_MODEL_PATH", "models/test.gguf")
    monkeypatch.setenv("LLM_CONTEXT_LENGTH", "4096")
    monkeypatch.setenv("LLM_MAX_TOKENS", "512")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("LLM_N_GPU_LAYERS", "-1")


@pytest.mark.usefixtures("clean_env")
class TestLLMSettings:
    """Tests for LLMSettings class."""

    @staticmethod
    def test_missing_required_fields() -> None:
        """Missing required fields raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(_env_file=None)
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "LLM_MODEL_PATH" for e in errors)

    @staticmethod
    def test_absolute_model_path_is_absolute(llm_env_vars: None) -> None:
        """absolute_model_path returns an absolute Path."""
        s = LLMSettings(_env_file=None)
        assert isinstance(s.absolute_model_path, Path)
        assert s.absolute_model_path.is_absolute()

    @staticmethod
    def test_is_configured_false_when_model_missing(llm_env_vars: None) -> None:
        """is_configured returns False when model file does not exist."""
        s = LLMSettings(_env_file=None)
        assert s.is_configured is False

    @staticmethod
    def test_temperature_boundary_low(llm_env_vars: None) -> None:
        """Temperature 0.0 is accepted."""
        s = LLMSettings(_env_file=None, temperature=0.0)
        assert s.temperature == approx(0.0)

    @staticmethod
    def test_temperature_boundary_high(llm_env_vars: None) -> None:
        """Temperature 2.0 is accepted."""
        s = LLMSettings(_env_file=None, temperature=2.0)
        assert s.temperature == approx(2.0)

    @staticmethod
    def test_temperature_invalid_low(monkeypatch: pytest.MonkeyPatch, llm_env_vars: None) -> None:
        """Temperature below 0.0 raises ValidationError."""
        monkeypatch.setenv("LLM_TEMPERATURE", "-0.1")
        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @staticmethod
    def test_temperature_invalid_high(monkeypatch: pytest.MonkeyPatch, llm_env_vars: None) -> None:
        """Temperature above 2.0 raises ValidationError."""
        monkeypatch.setenv("LLM_TEMPERATURE", "2.1")
        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @staticmethod
    def test_context_length_invalid(monkeypatch: pytest.MonkeyPatch, llm_env_vars: None) -> None:
        """Non-positive context length raises ValidationError."""
        monkeypatch.setenv("LLM_CONTEXT_LENGTH", "0")
        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @staticmethod
    def test_max_tokens_invalid(monkeypatch: pytest.MonkeyPatch, llm_env_vars: None) -> None:
        """Non-positive max tokens raises ValidationError."""
        monkeypatch.setenv("LLM_MAX_TOKENS", "-1")
        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @staticmethod
    def test_env_override(monkeypatch: pytest.MonkeyPatch, llm_env_vars: None) -> None:
        """Environment variables override values."""
        monkeypatch.setenv("LLM_CONTEXT_LENGTH", "8192")
        monkeypatch.setenv("LLM_MAX_TOKENS", "1024")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
        s = LLMSettings(_env_file=None)
        assert s.context_length == 8192
        assert s.max_tokens == 1024
        assert s.temperature == pytest.approx(0.3)


# =============================================================================
# CLASSIFIER SETTINGS
# =============================================================================


@pytest.fixture
def classifier_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required Classifier environment variables."""
    monkeypatch.setenv("CLASSIFIER_MODEL_NAME", "MoritzLaurer/DeBERTa-v3-base-zeroshot-v2.0")
    monkeypatch.setenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.4")
    monkeypatch.setenv("CLASSIFIER_DEVICE", "auto")


@pytest.mark.usefixtures("clean_env")
class TestClassifierSettings:
    """Tests for ClassifierSettings class."""

    @staticmethod
    def test_missing_required_fields() -> None:
        """Missing required fields raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ClassifierSettings(_env_file=None)
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "CLASSIFIER_MODEL_NAME" for e in errors)

    @staticmethod
    def test_confidence_threshold_boundary_low(classifier_env_vars: None) -> None:
        """Confidence 0.0 is accepted."""
        s = ClassifierSettings(_env_file=None, confidence_threshold=0.0)
        assert s.confidence_threshold == approx(0.0)

    @staticmethod
    def test_confidence_threshold_boundary_high(classifier_env_vars: None) -> None:
        """Confidence 1.0 is accepted."""
        s = ClassifierSettings(_env_file=None, confidence_threshold=1.0)
        assert s.confidence_threshold == approx(1.0)

    @staticmethod
    def test_confidence_threshold_invalid_low(
        monkeypatch: pytest.MonkeyPatch, classifier_env_vars: None
    ) -> None:
        """Threshold below 0.0 raises ValidationError."""
        monkeypatch.setenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "-0.1")
        with pytest.raises(ValidationError):
            ClassifierSettings(_env_file=None)

    @staticmethod
    def test_confidence_threshold_invalid_high(
        monkeypatch: pytest.MonkeyPatch, classifier_env_vars: None
    ) -> None:
        """Threshold above 1.0 raises ValidationError."""
        monkeypatch.setenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "1.1")
        with pytest.raises(ValidationError):
            ClassifierSettings(_env_file=None)

    @staticmethod
    def test_device_valid_values(
        monkeypatch: pytest.MonkeyPatch, classifier_env_vars: None
    ) -> None:
        """Valid device values are accepted and lowercased."""
        for device in ["cpu", "cuda", "auto", "CPU", "CUDA", "Auto"]:
            monkeypatch.setenv("CLASSIFIER_DEVICE", device)
            s = ClassifierSettings(_env_file=None)
            assert s.device in {"cpu", "cuda", "auto"}

    @staticmethod
    def test_device_invalid(monkeypatch: pytest.MonkeyPatch, classifier_env_vars: None) -> None:
        """Invalid device raises ValidationError."""
        monkeypatch.setenv("CLASSIFIER_DEVICE", "tpu")
        with pytest.raises(ValidationError):
            ClassifierSettings(_env_file=None)


# =============================================================================
# EMBEDDING SETTINGS
# =============================================================================


@pytest.fixture
def embedding_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required Embedding environment variables."""
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "384")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "64")


@pytest.mark.usefixtures("clean_env")
class TestEmbeddingSettings:
    """Tests for EmbeddingSettings class."""

    @staticmethod
    def test_missing_required_fields() -> None:
        """Missing required fields raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingSettings(_env_file=None)
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "EMBEDDING_MODEL_NAME" for e in errors)

    @staticmethod
    def test_config_values(embedding_env_vars: None) -> None:
        """Configured embedding settings match environment."""
        s = EmbeddingSettings(_env_file=None)
        assert s.model_name == "all-MiniLM-L6-v2"
        assert s.dimensions == 384
        assert s.batch_size == 64

    @staticmethod
    def test_dimensions_invalid(monkeypatch: pytest.MonkeyPatch, embedding_env_vars: None) -> None:
        """Non-positive dimensions raises ValidationError."""
        monkeypatch.setenv("EMBEDDING_DIMENSIONS", "0")
        with pytest.raises(ValidationError):
            EmbeddingSettings(_env_file=None)

    @staticmethod
    def test_batch_size_invalid(monkeypatch: pytest.MonkeyPatch, embedding_env_vars: None) -> None:
        """Non-positive batch size raises ValidationError."""
        monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "0")
        with pytest.raises(ValidationError):
            EmbeddingSettings(_env_file=None)

    @staticmethod
    def test_env_override(monkeypatch: pytest.MonkeyPatch, embedding_env_vars: None) -> None:
        """Environment variables can be overridden."""
        monkeypatch.setenv("EMBEDDING_MODEL_NAME", "all-mpnet-base-v2")
        monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")
        s = EmbeddingSettings(_env_file=None)
        assert s.model_name == "all-mpnet-base-v2"
        assert s.dimensions == 768
