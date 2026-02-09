"""LLM service wrapping llama-cpp-python.

Provides local LLM inference for the HorrorBot chatbot
using GGUF models via llama.cpp bindings.
"""

from collections.abc import Iterator
from functools import lru_cache

from src.etl.utils.logger import setup_logger
from src.settings import settings

logger = setup_logger("services.llm")


class LLMService:
    """Local LLM inference service using llama-cpp-python.

    Loads a GGUF model and provides text generation
    with configurable parameters. The model is lazy-loaded
    on first use to avoid startup overhead.

    Attributes:
        _model_path: Absolute path to GGUF model file.
        _context_length: Context window size in tokens.
        _max_tokens: Default maximum tokens per response.
        _temperature: Default sampling temperature.
        _n_gpu_layers: GPU layers for offloading.
        _timeout: Inference timeout in seconds.
        _llm: Lazy-loaded Llama model instance.
    """

    def __init__(
        self,
        model_path: str | None = None,
        context_length: int | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        n_gpu_layers: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        """Initialize LLM service from settings or explicit parameters.

        Args:
            model_path: Override model path from settings.
            context_length: Override context length from settings.
            max_tokens: Override max tokens from settings.
            temperature: Override temperature from settings.
            n_gpu_layers: Override GPU layers from settings.
            timeout_seconds: Override timeout from settings.
        """
        llm_settings = settings.llm
        self._model_path = model_path or str(llm_settings.absolute_model_path)
        self._context_length = context_length or llm_settings.context_length
        self._max_tokens = max_tokens or llm_settings.max_tokens
        self._temperature = temperature if temperature is not None else llm_settings.temperature
        self._n_gpu_layers = n_gpu_layers if n_gpu_layers is not None else llm_settings.n_gpu_layers
        self._timeout = timeout_seconds or llm_settings.timeout_seconds
        self._llm = None
        self._logger = logger

    @property
    def llm(self):
        """Lazy-load and return the Llama model."""
        if self._llm is None:
            from llama_cpp import Llama

            self._logger.info(
                "loading_llm",
                model_path=self._model_path,
                context_length=self._context_length,
                n_gpu_layers=self._n_gpu_layers,
            )
            self._llm = Llama(
                model_path=self._model_path,
                n_ctx=self._context_length,
                n_gpu_layers=self._n_gpu_layers,
                verbose=False,
            )
            self._logger.info("llm_loaded")
        return self._llm

    def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop: list[str] | None = None,
    ) -> dict:
        """Generate text completion from a prompt.

        Args:
            prompt: Input prompt text.
            max_tokens: Override max tokens for this call.
            temperature: Override temperature for this call.
            stop: Stop sequences to halt generation.

        Returns:
            Dict with keys:
                - text: Generated text.
                - usage: Token usage stats (prompt_tokens, completion_tokens, total_tokens).
        """
        result = self.llm.create_completion(
            prompt=prompt,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature if temperature is not None else self._temperature,
            stop=stop or [],
        )

        return {
            "text": result["choices"][0]["text"],
            "usage": result.get("usage", {}),
        }

    def generate_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Generate chat completion from a message list.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                Roles: 'system', 'user', 'assistant'.
            max_tokens: Override max tokens for this call.
            temperature: Override temperature for this call.

        Returns:
            Dict with keys:
                - text: Generated assistant response.
                - usage: Token usage stats.
        """
        result = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature if temperature is not None else self._temperature,
        )

        return {
            "text": result["choices"][0]["message"]["content"],
            "usage": result.get("usage", {}),
        }

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream chat completion token by token.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            max_tokens: Override max tokens for this call.
            temperature: Override temperature for this call.

        Yields:
            Generated text chunks as they become available.
        """
        stream = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens or self._max_tokens,
            temperature=temperature if temperature is not None else self._temperature,
            stream=True,
        )

        for chunk in stream:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content

    @property
    def model_path(self) -> str:
        """Return model path."""
        return self._model_path

    @property
    def context_length(self) -> int:
        """Return context length."""
        return self._context_length


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """Get singleton LLM service instance.

    Returns:
        Cached LLMService instance.
    """
    return LLMService()
