"""Non-regression tests for DocumentRetriever.

Guards against index-disabling SQL statements (SET LOCAL enable_indexscan/
enable_bitmapscan = off) that caused the 2026-03-13 performance incident.

See: incidents/INCIDENT_REPORT.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.rag.retriever import DocumentRetriever


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session with a single result row."""
    session = MagicMock()
    mock_row = MagicMock()
    mock_row.id = "00000000-0000-0000-0000-000000000001"
    mock_row.content = "Test horror film content"
    mock_row.source_type = "film_overview"
    mock_row.source_id = 123
    mock_row.metadata = {"title": "Test Film", "year": 2020}
    mock_row.similarity = 0.85
    session.execute.return_value = [mock_row]
    return session


@pytest.fixture
def retriever(mock_session):
    """DocumentRetriever with mocked embedding service and session."""
    with patch("src.services.rag.retriever.get_embedding_service"):
        ret = DocumentRetriever(match_count=5, similarity_threshold=0.7)
    ret._session_factory = MagicMock(return_value=mock_session)
    return ret


# ===========================================================================
# Non-regression: index-disabling SQL must never appear
# ===========================================================================


class TestRetrieverIndexGuard:
    """Guard against SET LOCAL statements that disable PostgreSQL indexes.

    Incident 2026-03-13: SET LOCAL enable_indexscan = off caused sequential
    scans on 31k+ vector documents, degrading RAG retrieval by x4 (cached)
    to x30-50 (cold cache in production).
    """

    @staticmethod
    def test_execute_search_never_disables_indexscan(retriever, mock_session):
        """_execute_search must NOT execute SET LOCAL enable_indexscan = off."""
        retriever._execute_search(
            embedding=[0.1] * 384,
            match_count=5,
            threshold=0.7,
            source_type=None,
        )

        executed_sql = [
            str(call_args[0][0])
            for call_args in mock_session.execute.call_args_list
        ]

        for sql in executed_sql:
            assert "enable_indexscan" not in sql.lower(), (
                f"Regression detected: '{sql}' disables index scan. "
                "See incidents/INCIDENT_REPORT.md (2026-03-13)."
            )

    @staticmethod
    def test_execute_search_never_disables_bitmapscan(retriever, mock_session):
        """_execute_search must NOT execute SET LOCAL enable_bitmapscan = off."""
        retriever._execute_search(
            embedding=[0.1] * 384,
            match_count=5,
            threshold=0.7,
            source_type=None,
        )

        executed_sql = [
            str(call_args[0][0])
            for call_args in mock_session.execute.call_args_list
        ]

        for sql in executed_sql:
            assert "enable_bitmapscan" not in sql.lower(), (
                f"Regression detected: '{sql}' disables bitmap scan. "
                "See incidents/INCIDENT_REPORT.md (2026-03-13)."
            )

    @staticmethod
    def test_execute_search_only_runs_search_query(retriever, mock_session):
        """_execute_search should execute exactly ONE SQL statement."""
        retriever._execute_search(
            embedding=[0.1] * 384,
            match_count=5,
            threshold=0.7,
            source_type=None,
        )

        assert mock_session.execute.call_count == 1, (
            f"Expected 1 SQL call (search query only), got "
            f"{mock_session.execute.call_count}. Extra calls may indicate "
            "SET LOCAL or other injected statements."
        )

    @staticmethod
    def test_execute_search_calls_search_function(retriever, mock_session):
        """_execute_search calls the search_similar_documents SQL function."""
        retriever._execute_search(
            embedding=[0.1] * 384,
            match_count=5,
            threshold=0.7,
            source_type=None,
        )

        sql_text = str(mock_session.execute.call_args_list[0][0][0])
        assert "search_similar_documents" in sql_text

    @staticmethod
    def test_execute_search_closes_session(retriever, mock_session):
        """Session is always closed after search."""
        retriever._execute_search(
            embedding=[0.1] * 384,
            match_count=5,
            threshold=0.7,
            source_type=None,
        )

        mock_session.close.assert_called_once()

    @staticmethod
    def test_execute_search_closes_session_on_error(retriever, mock_session):
        """Session is closed even when the search query raises an exception."""
        mock_session.execute.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            retriever._execute_search(
                embedding=[0.1] * 384,
                match_count=5,
                threshold=0.7,
                source_type=None,
            )

        mock_session.close.assert_called_once()
