"""T3 — Unit tests for RAGPipeline orchestration logic.

Tests the RAG pipeline coordination with fully mocked dependencies:
retriever, LLM service, and prompt builder. Focuses on:
- Call sequencing and argument passing
- Timing measurements (mocked perf_counter)
- Prometheus metrics recording (_record_llm_metrics)
- Result assembly (RAGResult fields)
- Error metric increments on failure

Run:
    pytest tests/unit/test_rag_pipeline.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from src.services.rag.pipeline import RAGPipeline, RAGResult
from src.services.rag.retriever import RetrievedDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(
    retriever: MagicMock | None = None,
    llm_service: MagicMock | None = None,
) -> RAGPipeline:
    """Build a RAGPipeline with mocked dependencies."""
    return RAGPipeline(
        retriever=retriever or MagicMock(),
        llm_service=llm_service or MagicMock(),
    )


# =========================================================================
# T3 — execute() synchronous pipeline
# =========================================================================


class TestRAGPipelineExecute:
    """T3 — Synchronous execute() orchestration."""

    @staticmethod
    def test_execute_calls_retriever_with_message(
        sample_documents, mock_llm_service
    ):
        """Retriever is called with the user message."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        pipeline.execute(
            intent="horror_recommendation",
            user_message="Recommande un film d'horreur",
            history=[],
        )

        mock_retriever.retrieve.assert_called_once_with("Recommande un film d'horreur")

    @staticmethod
    @patch("src.services.rag.pipeline.RAGPromptBuilder.build")
    def test_execute_passes_docs_to_prompt_builder(
        mock_build, sample_documents, mock_llm_service
    ):
        """Prompt builder receives intent, message, documents, and history."""
        mock_build.return_value = [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        history = [{"role": "user", "content": "Salut"}]
        pipeline.execute(
            intent="horror_recommendation",
            user_message="Recommande un film",
            history=history,
        )

        mock_build.assert_called_once_with(
            intent="horror_recommendation",
            user_message="Recommande un film",
            documents=sample_documents,
            history=history,
        )

    @staticmethod
    @patch("src.services.rag.pipeline.RAGPromptBuilder.build")
    def test_execute_calls_llm_with_built_messages(
        mock_build, sample_documents, mock_llm_service
    ):
        """LLM generate_chat is called with messages from prompt builder."""
        built_messages = [
            {"role": "system", "content": "Tu es un expert."},
            {"role": "user", "content": "Recommande un film"},
        ]
        mock_build.return_value = built_messages
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        pipeline.execute(
            intent="horror_recommendation",
            user_message="Recommande un film",
            history=[],
        )

        mock_llm_service.generate_chat.assert_called_once_with(built_messages)

    @staticmethod
    @patch("src.services.rag.pipeline.time.perf_counter")
    def test_execute_timing_uses_perf_counter(
        mock_perf, sample_documents, mock_llm_service
    ):
        """Timing measurements use perf_counter for retrieval and generation."""
        # Sequence: retrieval_start=0.0, retrieval_end=0.050, gen_start=0.055, gen_end=0.255
        mock_perf.side_effect = [0.0, 0.050, 0.055, 0.255]
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        result = pipeline.execute(
            intent="horror_recommendation",
            user_message="Test",
            history=[],
        )

        assert result.retrieval_time_ms == pytest.approx(50.0, abs=0.1)
        assert result.generation_time_ms == pytest.approx(200.0, abs=0.1)

    @staticmethod
    def test_execute_assembles_rag_result(sample_documents, mock_llm_service):
        """RAGResult fields are correctly populated from pipeline outputs."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        result = pipeline.execute(
            intent="horror_trivia",
            user_message="Qui a realise L'Exorciste ?",
            history=[],
        )

        assert isinstance(result, RAGResult)
        assert result.intent == "horror_trivia"
        assert result.text == mock_llm_service.generate_chat.return_value["text"]
        assert result.documents == sample_documents
        assert result.usage == mock_llm_service.generate_chat.return_value.get("usage", {})
        assert result.retrieval_time_ms >= 0.0
        assert result.generation_time_ms >= 0.0

    @staticmethod
    def test_execute_with_empty_documents(mock_llm_service):
        """Pipeline handles empty retriever results without crashing."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        result = pipeline.execute(
            intent="horror_recommendation",
            user_message="Film tres obscur",
            history=[],
        )

        assert result.text is not None
        assert len(result.documents) == 0

    @staticmethod
    @patch("src.services.rag.pipeline.LLM_REQUESTS_TOTAL")
    def test_execute_increments_success_metric(
        mock_metric, sample_documents, mock_llm_service
    ):
        """Success counter is incremented on successful execution."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        pipeline.execute(intent="horror_recommendation", user_message="Test", history=[])

        mock_metric.labels.assert_called_with(status="success")
        mock_metric.labels(status="success").inc.assert_called_once()

    @staticmethod
    @patch("src.services.rag.pipeline.LLM_REQUESTS_TOTAL")
    def test_execute_increments_error_metric_on_failure(
        mock_metric, sample_documents
    ):
        """Error counter is incremented when LLM raises an exception."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        mock_llm = MagicMock()
        mock_llm.generate_chat.side_effect = RuntimeError("OOM")
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm)

        with pytest.raises(RuntimeError, match="OOM"):
            pipeline.execute(intent="horror_recommendation", user_message="Test", history=[])

        mock_metric.labels.assert_called_with(status="error")
        mock_metric.labels(status="error").inc.assert_called_once()


# =========================================================================
# T3 — execute_stream() streaming pipeline
# =========================================================================


class TestRAGPipelineStream:
    """T3 — Streaming execute_stream() orchestration."""

    @staticmethod
    def test_stream_calls_retriever(sample_documents, mock_llm_service):
        """Retriever is called before streaming starts."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        pipeline.execute_stream(
            intent="horror_recommendation",
            user_message="Recommande un film",
            history=[],
        )

        mock_retriever.retrieve.assert_called_once_with("Recommande un film")

    @staticmethod
    def test_stream_returns_iterator_and_documents(sample_documents, mock_llm_service):
        """execute_stream returns (Iterator[str], list[RetrievedDocument])."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        token_stream, documents = pipeline.execute_stream(
            intent="horror_recommendation",
            user_message="Test",
            history=[],
        )

        assert hasattr(token_stream, "__iter__")
        assert isinstance(documents, list)
        assert len(documents) == len(sample_documents)
        assert all(isinstance(d, RetrievedDocument) for d in documents)

    @staticmethod
    @patch("src.services.rag.pipeline.RAGPromptBuilder.build")
    def test_stream_passes_built_messages_to_llm(
        mock_build, sample_documents, mock_llm_service
    ):
        """LLM generate_stream is called with messages from prompt builder."""
        built_messages = [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        mock_build.return_value = built_messages
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = sample_documents
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        pipeline.execute_stream(
            intent="horror_recommendation",
            user_message="Test",
            history=[],
        )

        mock_llm_service.generate_stream.assert_called_once_with(built_messages)

    @staticmethod
    def test_stream_propagates_retriever_error(mock_llm_service):
        """Retriever errors propagate to caller."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = ConnectionError("DB down")
        pipeline = _make_pipeline(retriever=mock_retriever, llm_service=mock_llm_service)

        with pytest.raises(ConnectionError, match="DB down"):
            pipeline.execute_stream(
                intent="horror_recommendation",
                user_message="Test",
                history=[],
            )


# =========================================================================
# T3 — _record_llm_metrics() static method
# =========================================================================


class TestRAGPipelineRecordMetrics:
    """T3 — Prometheus metrics recording via _record_llm_metrics."""

    @staticmethod
    @patch("src.services.rag.pipeline.LLM_REQUEST_DURATION")
    @patch("src.services.rag.pipeline.LLM_PROMPT_TOKENS")
    @patch("src.services.rag.pipeline.LLM_TOKENS_GENERATED")
    @patch("src.services.rag.pipeline.LLM_TOKENS_PER_SECOND")
    def test_record_metrics_observes_duration_and_tokens(
        mock_tps, mock_gen, mock_prompt, mock_duration
    ):
        """Duration, prompt tokens, and generated tokens are all recorded."""
        usage = {"prompt_tokens": 150, "completion_tokens": 40}

        RAGPipeline._record_llm_metrics(usage, duration_s=2.0)

        mock_duration.observe.assert_called_once_with(2.0)
        mock_prompt.inc.assert_called_once_with(150)
        mock_gen.inc.assert_called_once_with(40)
        mock_tps.set.assert_called_once_with(20.0)  # 40 / 2.0

    @staticmethod
    @patch("src.services.rag.pipeline.LLM_REQUEST_DURATION")
    @patch("src.services.rag.pipeline.LLM_PROMPT_TOKENS")
    @patch("src.services.rag.pipeline.LLM_TOKENS_GENERATED")
    @patch("src.services.rag.pipeline.LLM_TOKENS_PER_SECOND")
    def test_record_metrics_zero_duration_no_division_error(
        mock_tps, mock_gen, mock_prompt, mock_duration
    ):
        """Zero duration does not cause ZeroDivisionError."""
        usage = {"prompt_tokens": 100, "completion_tokens": 30}

        RAGPipeline._record_llm_metrics(usage, duration_s=0.0)

        mock_duration.observe.assert_called_once_with(0.0)
        mock_gen.inc.assert_called_once_with(30)
        # tokens_per_second should NOT be set when duration is 0
        mock_tps.set.assert_not_called()

    @staticmethod
    @patch("src.services.rag.pipeline.LLM_REQUEST_DURATION")
    @patch("src.services.rag.pipeline.LLM_PROMPT_TOKENS")
    @patch("src.services.rag.pipeline.LLM_TOKENS_GENERATED")
    @patch("src.services.rag.pipeline.LLM_TOKENS_PER_SECOND")
    def test_record_metrics_empty_usage_skips_token_counters(
        mock_tps, mock_gen, mock_prompt, mock_duration
    ):
        """Empty usage dict skips prompt/completion token counters."""
        RAGPipeline._record_llm_metrics({}, duration_s=1.0)

        mock_duration.observe.assert_called_once_with(1.0)
        mock_prompt.inc.assert_not_called()
        mock_gen.inc.assert_not_called()
        mock_tps.set.assert_not_called()
