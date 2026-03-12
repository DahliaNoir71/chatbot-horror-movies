"""Tests for Prometheus metrics definitions."""

import pytest
from prometheus_client import Counter, Gauge, Histogram, Info

from src.monitoring.metrics import (
    CLASSIFIER_CONFIDENCE,
    CLASSIFIER_REQUEST_DURATION,
    CLASSIFIER_REQUESTS_TOTAL,
    DB_CONNECTION_POOL_SIZE,
    DB_QUERY_DURATION,
    EMBEDDING_REQUEST_DURATION,
    LLM_PROMPT_TOKENS,
    LLM_REQUEST_DURATION,
    LLM_REQUESTS_TOTAL,
    LLM_TOKENS_GENERATED,
    LLM_TOKENS_PER_SECOND,
    MODEL_INFO,
    MODEL_MEMORY_BYTES,
)


class TestLLMMetrics:
    """Tests for LLM metric objects."""

    @staticmethod
    def test_llm_request_duration_is_histogram() -> None:
        assert isinstance(LLM_REQUEST_DURATION, Histogram)

    @staticmethod
    def test_llm_tokens_generated_is_counter() -> None:
        assert isinstance(LLM_TOKENS_GENERATED, Counter)

    @staticmethod
    def test_llm_prompt_tokens_is_counter() -> None:
        assert isinstance(LLM_PROMPT_TOKENS, Counter)

    @staticmethod
    def test_llm_tokens_per_second_is_gauge() -> None:
        assert isinstance(LLM_TOKENS_PER_SECOND, Gauge)

    @staticmethod
    def test_llm_requests_total_is_counter() -> None:
        assert isinstance(LLM_REQUESTS_TOTAL, Counter)


class TestClassifierMetrics:
    """Tests for classifier metric objects."""

    @staticmethod
    def test_classifier_duration_is_histogram() -> None:
        assert isinstance(CLASSIFIER_REQUEST_DURATION, Histogram)

    @staticmethod
    def test_classifier_requests_is_counter() -> None:
        assert isinstance(CLASSIFIER_REQUESTS_TOTAL, Counter)

    @staticmethod
    def test_classifier_confidence_is_histogram() -> None:
        assert isinstance(CLASSIFIER_CONFIDENCE, Histogram)


class TestEmbeddingMetrics:
    """Tests for embedding metric objects."""

    @staticmethod
    def test_embedding_duration_is_histogram() -> None:
        assert isinstance(EMBEDDING_REQUEST_DURATION, Histogram)


class TestSystemMetrics:
    """Tests for system-level metric objects."""

    @staticmethod
    def test_model_memory_is_gauge() -> None:
        assert isinstance(MODEL_MEMORY_BYTES, Gauge)

    @staticmethod
    def test_model_info_is_info() -> None:
        assert isinstance(MODEL_INFO, Info)


class TestDatabaseMetrics:
    """Tests for database metric objects."""

    @staticmethod
    def test_db_query_duration_is_histogram() -> None:
        assert isinstance(DB_QUERY_DURATION, Histogram)

    @staticmethod
    def test_db_connection_pool_size_is_gauge() -> None:
        assert isinstance(DB_CONNECTION_POOL_SIZE, Gauge)


class TestMetricNames:
    """Tests that all metric names follow the horrorbot_ prefix convention."""

    @staticmethod
    @pytest.mark.parametrize("metric", [
        LLM_REQUEST_DURATION,
        LLM_TOKENS_GENERATED,
        LLM_PROMPT_TOKENS,
        LLM_TOKENS_PER_SECOND,
        LLM_REQUESTS_TOTAL,
        CLASSIFIER_REQUEST_DURATION,
        CLASSIFIER_REQUESTS_TOTAL,
        CLASSIFIER_CONFIDENCE,
        EMBEDDING_REQUEST_DURATION,
        MODEL_MEMORY_BYTES,
        DB_QUERY_DURATION,
        DB_CONNECTION_POOL_SIZE,
    ])
    def test_metric_has_horrorbot_prefix(metric) -> None:
        """All metrics start with 'horrorbot_'."""
        assert metric._name.startswith("horrorbot_")
