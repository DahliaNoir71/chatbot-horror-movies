"""LLM service wrapping llama-cpp-python.

Provides local LLM inference for the HorrorBot chatbot
using GGUF models via llama.cpp bindings.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

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
        _n_gpu_layers: Layers offloaded (0 = CPU only).
        _n_threads: CPU threads used for inference.
        _n_batch: Prompt processing batch size.
        _warmup_enabled: Whether to warm up the model after load.
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
        n_threads: int | None = None,
        n_batch: int | None = None,
        warmup_enabled: bool | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        """Initialize LLM service from settings or explicit parameters.

        Args:
            model_path: Override model path from settings.
            context_length: Override context length from settings.
            max_tokens: Override max tokens from settings.
            temperature: Override temperature from settings.
            n_gpu_layers: Override layers from settings (0 = CPU only).
            n_threads: Override CPU threads from settings (None = auto).
            n_batch: Override prompt batch size from settings.
            warmup_enabled: Override warmup flag from settings.
            timeout_seconds: Override timeout from settings.
        """
        llm_settings = settings.llm
        self._model_path = model_path or str(llm_settings.absolute_model_path)
        self._context_length = context_length or llm_settings.context_length
        self._max_tokens = max_tokens or llm_settings.max_tokens
        self._temperature = temperature if temperature is not None else llm_settings.temperature
        self._n_gpu_layers = n_gpu_layers if n_gpu_layers is not None else llm_settings.n_gpu_layers
        self._n_threads = n_threads if n_threads is not None else llm_settings.n_threads
        self._n_batch = n_batch or llm_settings.n_batch
        self._warmup_enabled = (
            warmup_enabled if warmup_enabled is not None else llm_settings.warmup_enabled
        )
        self._timeout = timeout_seconds or llm_settings.timeout_seconds
        self._llm: Any = None
        self._logger = logger

    # -------------------------------------------------------------------------
    # Model loading
    # -------------------------------------------------------------------------

    @property
    def llm(self) -> Any:
        """Lazy-load and return the Llama model."""
        if self._llm is None:
            self._llm = self._load_llama()
            if self._warmup_enabled:
                self._warmup()
        return self._llm

    def _load_llama(self) -> Any:
        """Instantiate the Llama model with optimized loading parameters.

        Key flags for fast cold starts:
            - ``use_mmap=True``: maps the GGUF file into virtual memory. The
              OS loads pages on demand, turning a 60-120s full read into a
              near-instant operation.
            - ``use_mlock=False``: avoids locking pages in RAM, preventing
              swap pressure in resource-constrained containers.
            - ``n_threads`` / ``n_batch``: taken from settings for
              reproducibility across environments.

        Returns:
            Configured ``Llama`` instance.
        """
        from llama_cpp import Llama

        self._logger.info(
            "Loading LLM: %s (ctx=%d, gpu_layers=%d, threads=%s, batch=%d)",
            self._model_path,
            self._context_length,
            self._n_gpu_layers,
            self._n_threads if self._n_threads is not None else "auto",
            self._n_batch,
        )
        llm = Llama(
            model_path=self._model_path,
            n_ctx=self._context_length,
            n_gpu_layers=self._n_gpu_layers,
            n_threads=self._n_threads,
            n_batch=self._n_batch,
            use_mmap=True,
            use_mlock=False,
            verbose=False,
        )
        self._logger.info("LLM loaded successfully")
        return llm

    def _warmup(self) -> None:
        """Force a 1-token generation to pre-fault pages and build caches.

        With ``use_mmap=True``, the first real user request would otherwise
        pay the cost of loading model pages from disk on demand. A tiny dummy
        generation pulls the hot pages into RAM and warms internal buffers,
        keeping the first user-facing response fast.
        """
        self._logger.info("Warming up LLM (1 token)...")
        try:
            self._llm.create_completion(prompt="Hi", max_tokens=1, temperature=0.0)
            self._logger.info("LLM warmup complete")
        except Exception:  # noqa: BLE001 — warmup failure must not block boot
            self._logger.warning("LLM warmup failed (non-fatal)", exc_info=True)

    # -------------------------------------------------------------------------
    # Generation methods
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Accessors
    # -------------------------------------------------------------------------

    @property
    def model_path(self) -> str:
        """Return model path."""
        return self._model_path

    @property
    def context_length(self) -> int:
        """Return context length."""
        return self._context_length

    @property
    def is_loaded(self) -> bool:
        """Return whether the underlying Llama model is loaded.

        Exposed as a public accessor so health checks don't reach into the
        private ``_llm`` attribute.
        """
        return self._llm is not None


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """Get singleton LLM service instance.

    Returns:
        Cached LLMService instance.
    """
    return LLMService()
