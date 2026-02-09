"""AI service configuration settings.

LLM, intent classifier, and embedding settings for E2 (C8).
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.base import get_project_root

# =============================================================================
# LLM SETTINGS
# =============================================================================


class LLMSettings(BaseSettings):
    """Local LLM configuration (llama-cpp-python).

    Attributes:
        model_path: Path to GGUF model file (relative to project root or absolute).
        context_length: Context window size in tokens.
        max_tokens: Maximum tokens to generate per response.
        temperature: Sampling temperature (0.0 = deterministic, 2.0 = creative).
        timeout_seconds: Inference timeout.
        n_gpu_layers: Layers to offload to GPU (-1 = all, 0 = CPU only).
    """

    model_path: str = Field(alias="LLM_MODEL_PATH")
    context_length: int = Field(alias="LLM_CONTEXT_LENGTH")
    max_tokens: int = Field(alias="LLM_MAX_TOKENS")
    temperature: float = Field(alias="LLM_TEMPERATURE")
    timeout_seconds: int = Field(alias="LLM_TIMEOUT_SECONDS")
    n_gpu_layers: int = Field(alias="LLM_N_GPU_LAYERS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("LLM_TEMPERATURE must be between 0.0 and 2.0")
        return v

    @field_validator("context_length")
    @classmethod
    def validate_context_length(cls, v: int) -> int:
        """Validate context length is positive."""
        if v <= 0:
            raise ValueError("LLM_CONTEXT_LENGTH must be > 0")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max tokens is positive."""
        if v <= 0:
            raise ValueError("LLM_MAX_TOKENS must be > 0")
        return v

    @property
    def absolute_model_path(self) -> Path:
        """Return absolute path to model file."""
        path = Path(self.model_path)
        if path.is_absolute():
            return path
        return get_project_root() / path

    @property
    def is_configured(self) -> bool:
        """Check if model file exists on disk."""
        return self.absolute_model_path.exists()


# =============================================================================
# CLASSIFIER SETTINGS
# =============================================================================


class ClassifierSettings(BaseSettings):
    """Intent classifier configuration (DeBERTa-v3 zero-shot).

    Attributes:
        model_name: HuggingFace model name for zero-shot classification.
        confidence_threshold: Minimum confidence to accept a classification.
        device: Inference device (cpu, cuda, auto).
    """

    model_name: str = Field(alias="CLASSIFIER_MODEL_NAME")
    confidence_threshold: float = Field(alias="CLASSIFIER_CONFIDENCE_THRESHOLD")
    device: str = Field(alias="CLASSIFIER_DEVICE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("confidence_threshold")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        """Validate confidence threshold is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("CLASSIFIER_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device is a recognized option."""
        valid_devices = {"cpu", "cuda", "auto"}
        v_lower = v.lower()
        if v_lower not in valid_devices:
            raise ValueError(f"CLASSIFIER_DEVICE must be one of {valid_devices}")
        return v_lower


# =============================================================================
# EMBEDDING SETTINGS
# =============================================================================


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration (sentence-transformers).

    Defaults match existing constants in embedding_service.py
    for backward compatibility.

    Attributes:
        model_name: Sentence-transformer model name.
        dimensions: Embedding vector dimensions (must match pgvector schema).
        batch_size: Batch size for bulk encoding.
    """

    model_name: str = Field(alias="EMBEDDING_MODEL_NAME")
    dimensions: int = Field(alias="EMBEDDING_DIMENSIONS")
    batch_size: int = Field(alias="EMBEDDING_BATCH_SIZE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        """Validate dimensions is positive."""
        if v <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be > 0")
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """Validate batch size is positive."""
        if v <= 0:
            raise ValueError("EMBEDDING_BATCH_SIZE must be > 0")
        return v
