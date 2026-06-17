"""RAG pipeline orchestrating retrieval, prompt building, and LLM generation.

Combines DocumentRetriever, RAGPromptBuilder, and LLMService
into a single pipeline for RAG-based intents.
"""

import asyncio
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from src.etl.utils.logger import setup_logger
from src.monitoring.metrics import (
    LLM_PROMPT_TOKENS,
    LLM_REQUEST_DURATION,
    LLM_REQUESTS_TOTAL,
    LLM_TOKENS_GENERATED,
    LLM_TOKENS_PER_SECOND,
    RAG_NO_CONTEXT_RESPONSES,
    RAG_NO_CONTEXT_RESPONSES_TOTAL,
    RAG_TRUSTED_DOCS_AFTER_RERANK,
)
from src.services.intent.prompts import SYSTEM_PROMPT_GENRE
from src.services.llm.llm_service import LLMService, get_llm_service
from src.services.rag.hybrid_retriever import HybridRetriever, get_hybrid_retriever
from src.services.rag.prompt_builder import RAGPromptBuilder
from src.services.rag.reranker import RerankerService, get_reranker_service
from src.services.rag.retriever import DocumentRetriever, RetrievedDocument
from src.settings import settings
from src.settings.retrieval import RetrievalSettings

logger = setup_logger("services.rag.pipeline")

# Templated refusal returned by the anti-hallucination circuit breaker when no
# retrieved document clears the rerank confidence threshold.
_NO_CONTEXT_MESSAGE = (
    "Je n'ai pas trouvé d'information fiable dans ma base de films "
    "sur ce sujet. Peux-tu reformuler ou préciser ta question ?"
)

# RRF constant for blending the cross-encoder rank with the retrieval-prior rank.
# Smaller than the retrieval-level rrf_k (60): the reranked pool is short (~30),
# so a small k keeps enough spread between adjacent ranks to matter.
_BLEND_RRF_K = 10

# Prefix prepended to every open-knowledge fallback answer so the user always
# sees that it is NOT grounded in the film database (markdown italic).
_OPEN_FALLBACK_PREFIX = (
    "ℹ️ *Rien de fiable dans ma base de films sur ce point — voici ce que j'en "
    "sais de manière générale, à vérifier :*\n\n"
)

# History turns carried into the open-knowledge fallback prompt (3 turns).
_OPEN_HISTORY_MESSAGES = 6


def log_grounding(text: str, documents: list[RetrievedDocument]) -> None:
    """Log how many injected source titles the response actually cites.

    Faithfulness signal (log-only, never mutates the response): an answer that
    names none of the retrieved films is most likely ungrounded — pulled from
    the LLM's pre-training rather than the provided context.

    Args:
        text: The generated response text.
        documents: The documents injected into the prompt.
    """
    if not documents:
        return
    lowered = text.lower()
    cited = 0
    for doc in documents:
        meta = doc.metadata
        titles = (str(meta.get("title", "")).lower(), str(meta.get("title_fr", "")).lower())
        if any(title and title in lowered for title in titles):
            cited += 1
    logger.info("Grounding check: %d/%d injected source titles cited", cited, len(documents))
    if cited == 0:
        logger.warning("Ungrounded response: 0/%d injected sources cited", len(documents))


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class RAGResult:
    """Result from a RAG pipeline execution.

    Attributes:
        text: Generated response text.
        intent: The intent that triggered this pipeline.
        documents: Retrieved documents used as context.
        usage: Token usage stats from LLM.
        retrieval_time_ms: Time spent on vector retrieval.
        rerank_time_ms: Time spent on cross-encoder reranking.
        generation_time_ms: Time spent on LLM generation.
    """

    text: str
    intent: str
    documents: list[RetrievedDocument] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0
    generation_time_ms: float = 0.0


# =============================================================================
# RAG PIPELINE
# =============================================================================


class RAGPipeline:
    """Full RAG pipeline: retrieve -> rerank -> build prompt -> generate.

    Attributes:
        _retriever: Retriever exposing `.retrieve(query) -> list[RetrievedDocument]`.
            Defaults to the hybrid (vector + BM25 + popularity) retriever.
        _reranker: Cross-encoder reranker for precision filtering.
        _llm: LLM service for text generation.
    """

    def __init__(
        self,
        retriever: HybridRetriever | DocumentRetriever | None = None,
        reranker: RerankerService | None = None,
        llm_service: LLMService | None = None,
        retrieval_settings: RetrievalSettings | None = None,
    ) -> None:
        """Initialize pipeline with injectable dependencies.

        Args:
            retriever: Override retriever (for testing). Accepts any object
                exposing `.retrieve(query, match_count=...)` — the shared
                interface of `HybridRetriever` (sync adapter) and
                `DocumentRetriever`.
            reranker: Override reranker service (for testing).
            llm_service: Override LLM service (for testing).
            retrieval_settings: Override retrieval settings (for testing).
        """
        self._retriever = retriever or get_hybrid_retriever()
        self._reranker = reranker or get_reranker_service()
        self._llm = llm_service or get_llm_service()
        self._settings = retrieval_settings or settings.retrieval
        self._logger = logger

    async def execute(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> RAGResult:
        """Execute full RAG pipeline.

        Retrieval is awaited directly (async). CPU-bound rerank + LLM
        steps run via `asyncio.to_thread` so they don't block the loop.

        Args:
            intent: Classified intent.
            user_message: Current user query.
            history: Conversation history.

        Returns:
            RAGResult with generated text and metadata.
        """
        retrieval_start = time.perf_counter()
        documents = await self._retrieve(user_message)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        rerank_start = time.perf_counter()
        trusted_docs = await self._rerank_and_select(user_message, documents)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000
        RAG_TRUSTED_DOCS_AFTER_RERANK.observe(len(trusted_docs))

        if not trusted_docs:
            RAG_NO_CONTEXT_RESPONSES_TOTAL.inc()
            if self._settings.open_fallback_enabled:
                return await self._open_fallback(
                    intent, user_message, history, retrieval_ms, rerank_ms
                )
            return self._build_no_context_response(intent)

        self._log_sources(trusted_docs)
        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=trusted_docs,
            history=history,
        )

        gen_start = time.perf_counter()
        try:
            result = await asyncio.to_thread(self._llm.generate_chat, messages)
            gen_ms = (time.perf_counter() - gen_start) * 1000

            self._record_llm_metrics(result.get("usage", {}), gen_ms / 1000)
            LLM_REQUESTS_TOTAL.labels(status="success").inc()

            self._logger.info(
                f"RAG pipeline complete: "
                f"retrieval={round(retrieval_ms)}ms, "
                f"rerank={round(rerank_ms)}ms ({len(trusted_docs)} docs), "
                f"generation={round(gen_ms)}ms, "
                f"tokens={result.get('usage', {}).get('completion_tokens', '?')}, "
                f"total={round(retrieval_ms + rerank_ms + gen_ms)}ms"
            )

            log_grounding(result["text"], trusted_docs)
            return RAGResult(
                text=result["text"],
                intent=intent,
                documents=trusted_docs,
                usage=result.get("usage", {}),
                retrieval_time_ms=retrieval_ms,
                rerank_time_ms=rerank_ms,
                generation_time_ms=gen_ms,
            )
        except Exception:
            LLM_REQUESTS_TOTAL.labels(status="error").inc()
            raise

    async def execute_stream(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[Iterator[str], list[RetrievedDocument]]:
        """Execute RAG pipeline with streaming LLM output.

        Retrieval + rerank are async; the returned LLM token iterator is
        sync (consumed downstream by the SSE generator, which runs in
        Starlette's thread pool so the event loop stays free).

        Args:
            intent: Classified intent.
            user_message: Current user query.
            history: Conversation history.

        Returns:
            Tuple of (token iterator, retrieved documents).
        """
        documents = await self._retrieve(user_message)
        trusted_docs = await self._rerank_and_select(user_message, documents)

        self._logger.info(
            f"RAG stream retrieval: "
            f"{len(trusted_docs)} docs after rerank+blend "
            f"(top_similarity={round(trusted_docs[0].similarity, 3) if trusted_docs else 'N/A'}, "
            f"top_rerank={round(trusted_docs[0].rerank_score, 3) if trusted_docs and trusted_docs[0].rerank_score is not None else 'N/A'})"
        )

        RAG_TRUSTED_DOCS_AFTER_RERANK.observe(len(trusted_docs))
        if not trusted_docs:
            # Mirror execute(): open-knowledge fallback when enabled, else the
            # anti-hallucination circuit breaker (templated refusal).
            RAG_NO_CONTEXT_RESPONSES_TOTAL.inc()
            if self._settings.open_fallback_enabled:
                return self._open_fallback_stream(user_message, history), []
            RAG_NO_CONTEXT_RESPONSES.inc()
            return self._no_context_stream(), []

        self._log_sources(trusted_docs)
        messages = RAGPromptBuilder.build(
            intent=intent,
            user_message=user_message,
            documents=trusted_docs,
            history=history,
        )

        token_stream = self._llm.generate_stream(messages)
        return token_stream, trusted_docs

    async def answer_open(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Answer from open knowledge (no corpus grounding), with a disclaimer.

        For intents the synopsis corpus cannot ground (e.g. genre definitions):
        unlike the no-context fallback, the open path is chosen up front rather
        than after a failed retrieval, so no retrieval/rerank runs.

        Args:
            user_message: The user's query.
            history: Conversation history.

        Returns:
            The open-knowledge answer, prefixed with the "not from my database" notice.
        """
        messages = self._build_open_messages(user_message, history)
        result = await asyncio.to_thread(self._llm.generate_chat, messages)
        return _OPEN_FALLBACK_PREFIX + result["text"]

    def answer_open_stream(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        """Stream the open-knowledge answer: disclaimer prefix, then LLM tokens.

        Args:
            user_message: The user's query.
            history: Conversation history.

        Yields:
            The disclaimer prefix, then each generated token.
        """
        messages = self._build_open_messages(user_message, history)
        yield _OPEN_FALLBACK_PREFIX
        yield from self._llm.generate_stream(messages)

    async def _retrieve(self, user_message: str) -> list[RetrievedDocument]:
        """Dispatch to the retriever's async `search()` or sync `retrieve()`.

        `HybridRetriever` exposes an async `search()`; legacy/test mocks
        expose only sync `retrieve()`. The sync path is bridged via
        `asyncio.to_thread` so neither blocks the event loop.

        The async path requests `rerank_pool_top_k` candidates (not the final 5)
        so the cross-encoder reranks a wide pool instead of re-scoring the 5
        documents RRF already pre-selected.
        """
        search = getattr(self._retriever, "search", None)
        if search is not None and asyncio.iscoroutinefunction(search):
            return await search(user_message, top_k=self._settings.rerank_pool_top_k)
        return await asyncio.to_thread(self._retriever.retrieve, user_message)

    async def _rerank_and_select(
        self,
        query: str,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """Rerank the whole pool, blend with the retrieval prior, then cut.

        The cross-encoder scores every candidate; the final order is an RRF
        blend of the rerank rank and the RRF+popularity rank (see
        `_blend_rerank_with_prior`), so popular on-theme films the lexically
        biased reranker would bury still survive. Trust-filtering and the
        `final_top_k` cut are applied last.

        Args:
            query: User query.
            documents: Candidate pool from retrieval (carrying `final_score`).

        Returns:
            Trusted documents to inject into the prompt (length <= final_top_k).
        """
        if not documents:
            return []
        reranked = await asyncio.to_thread(self._reranker.rerank, query, documents, len(documents))
        blended = self._blend_rerank_with_prior(reranked)
        return self._filter_trusted(blended)[: self._settings.final_top_k]

    def _blend_rerank_with_prior(
        self,
        documents: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """Re-order reranked docs by RRF fusion of rerank rank and prior rank.

        The cross-encoder rewards query-term lexical overlap, which misranks
        thematic queries ("Body Snatcher" over "The Thing" for "body horror").
        Fusing its rank with the RRF+popularity prior's rank lets popular
        on-theme films survive. `rerank_blend_weight` tunes the balance
        (1.0 = pure rerank, 0.0 = pure prior). Ranks use list indices, so
        duplicate `source_id`s (test doubles) never collide.

        Args:
            documents: Reranked pool, each carrying `rerank_score` and the
                retrieval `final_score`.

        Returns:
            Documents ordered by the blended score, descending.
        """
        n = len(documents)
        if n <= 1:
            return documents
        by_rerank = sorted(range(n), key=lambda i: documents[i].rerank_score or 0.0, reverse=True)
        by_prior = sorted(range(n), key=lambda i: documents[i].final_score or 0.0, reverse=True)
        rerank_rank = [0] * n
        prior_rank = [0] * n
        for rank, i in enumerate(by_rerank, start=1):
            rerank_rank[i] = rank
        for rank, i in enumerate(by_prior, start=1):
            prior_rank[i] = rank
        w = self._settings.rerank_blend_weight

        def _blended(i: int) -> float:
            return w / (_BLEND_RRF_K + rerank_rank[i]) + (1.0 - w) / (_BLEND_RRF_K + prior_rank[i])

        return [documents[i] for i in sorted(range(n), key=_blended, reverse=True)]

    def _log_sources(self, documents: list[RetrievedDocument]) -> None:
        """Log the sources injected into the prompt for faithfulness audits.

        Records each document's TMDB id, title, similarity and rerank score so
        a generated answer can be checked against the exact context it was
        grounded on.

        Args:
            documents: Documents passed to the prompt builder.
        """
        sources = [
            f"tmdb={d.source_id} "
            f"'{d.metadata.get('title', '?')}' "
            f"sim={round(d.similarity, 3)} "
            f"rerank={round(d.rerank_score, 3) if d.rerank_score is not None else 'N/A'}"
            for d in documents
        ]
        self._logger.info("RAG sources injected (%d): %s", len(sources), " | ".join(sources))

    def _filter_trusted(self, documents: list[RetrievedDocument]) -> list[RetrievedDocument]:
        """Keep only documents that clear the rerank confidence threshold.

        Anti-hallucination gate shared by the buffered and streaming paths:
        documents scoring below `min_rerank_score` are dropped so the LLM is
        never grounded on weak context. Docs without a rerank score (e.g. test
        doubles) are kept.

        Args:
            documents: Reranked documents.

        Returns:
            Documents trusted enough to inject into the prompt.
        """
        return [
            d
            for d in documents
            if d.rerank_score is None or d.rerank_score >= self._settings.min_rerank_score
        ]

    @staticmethod
    def _no_context_stream() -> Iterator[str]:
        """Yield the templated refusal as a single-chunk stream.

        Streaming counterpart of `_build_no_context_response`, so the circuit
        breaker produces the same message whether or not the caller streams.

        Yields:
            The refusal message as one chunk.
        """
        yield _NO_CONTEXT_MESSAGE

    def _build_no_context_response(self, intent: str) -> RAGResult:
        """Build response when no document passed rerank confidence threshold.

        This is the anti-hallucination circuit breaker: when the retriever
        fails to find grounded context, we refuse to answer rather than let
        the LLM fabricate from pre-training.

        Args:
            intent: The intent that triggered this pipeline execution.

        Returns:
            RAGResult with a templated refusal message and no documents.
        """
        RAG_NO_CONTEXT_RESPONSES.inc()
        return RAGResult(text=_NO_CONTEXT_MESSAGE, intent=intent)

    async def _open_fallback(
        self,
        intent: str,
        user_message: str,
        history: list[dict[str, str]] | None,
        retrieval_ms: float,
        rerank_ms: float,
    ) -> RAGResult:
        """Answer from the LLM's general knowledge when retrieval found nothing.

        Deliberately un-grounded (no film allow-list); the response is prefixed
        with an explicit "not from my database" notice so the relaxation stays
        visible. Reached only when ``open_fallback_enabled`` is set.

        Args:
            intent: The triggering intent (kept in the result metadata).
            user_message: The user's query.
            history: Conversation history.
            retrieval_ms: Retrieval time already spent (carried to the result).
            rerank_ms: Rerank time already spent (carried to the result).

        Returns:
            RAGResult with the prefixed open-knowledge answer and no documents.
        """
        RAG_NO_CONTEXT_RESPONSES.inc()
        self._logger.info("Open-knowledge fallback used (no trusted context)")
        messages = self._build_open_messages(user_message, history)
        gen_start = time.perf_counter()
        result = await asyncio.to_thread(self._llm.generate_chat, messages)
        gen_ms = (time.perf_counter() - gen_start) * 1000
        self._record_llm_metrics(result.get("usage", {}), gen_ms / 1000)
        LLM_REQUESTS_TOTAL.labels(status="success").inc()
        return RAGResult(
            text=_OPEN_FALLBACK_PREFIX + result["text"],
            intent=intent,
            usage=result.get("usage", {}),
            retrieval_time_ms=retrieval_ms,
            rerank_time_ms=rerank_ms,
            generation_time_ms=gen_ms,
        )

    def _open_fallback_stream(
        self,
        user_message: str,
        history: list[dict[str, str]] | None,
    ) -> Iterator[str]:
        """Stream the open-knowledge fallback: disclaimer prefix, then LLM tokens.

        Args:
            user_message: The user's query.
            history: Conversation history.

        Yields:
            The disclaimer prefix, then each generated token.
        """
        RAG_NO_CONTEXT_RESPONSES.inc()
        self._logger.info("Open-knowledge fallback used (no trusted context, stream)")
        messages = self._build_open_messages(user_message, history)
        yield _OPEN_FALLBACK_PREFIX
        yield from self._llm.generate_stream(messages)

    @staticmethod
    def _build_open_messages(
        user_message: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        """Build the open-knowledge message list (system + bounded history + user).

        No retrieved context block and no allow-list — this is the un-grounded
        path. History is truncated to the last few turns for conversational
        continuity.

        Args:
            user_message: The user's query.
            history: Conversation history.

        Returns:
            Message list for the LLM.
        """
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT_GENRE}]
        if history:
            messages.extend(history[-_OPEN_HISTORY_MESSAGES:])
        messages.append({"role": "user", "content": user_message})
        return messages

    @staticmethod
    def _record_llm_metrics(usage: dict[str, Any], duration_s: float) -> None:
        """Record LLM performance metrics.

        Args:
            usage: Token usage stats from LLM.
            duration_s: Generation duration in seconds.
        """
        LLM_REQUEST_DURATION.observe(duration_s)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        if prompt_tokens:
            LLM_PROMPT_TOKENS.inc(prompt_tokens)
        if completion_tokens:
            LLM_TOKENS_GENERATED.inc(completion_tokens)
            if duration_s > 0:
                LLM_TOKENS_PER_SECOND.set(completion_tokens / duration_s)
