"""Unit tests for FilmographyService: name extraction, formatting, lookup."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.services.filmography.filmography_service import FilmographyService


class TestExtractName:
    @staticmethod
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("Films d'horreur réalisés par James Wan", "James Wan"),
            ("Filmographie horreur de Jordan Peele", "Jordan Peele"),
            ("Dans quels films d'horreur joue Sigourney Weaver ?", "Sigourney Weaver"),
            ("Quels films d'horreur avec Toni Collette ?", "Toni Collette"),
            ("Les films de Dario Argento", "Dario Argento"),
        ],
    )
    def test_extracts_trailing_name(message, expected) -> None:
        assert FilmographyService._extract_name(message) == expected

    @staticmethod
    def test_no_trigger_returns_none() -> None:
        assert FilmographyService._extract_name("Recommande un slasher") is None


class TestFormat:
    @staticmethod
    def test_empty_films() -> None:
        msg = FilmographyService._format("James Wan", [])
        assert "aucun film" in msg.lower()
        assert "James Wan" in msg

    @staticmethod
    def test_lists_films_with_count() -> None:
        msg = FilmographyService._format("James Wan", [("Saw", 2004), ("Insidious", 2010)])
        assert "Saw (2004)" in msg
        assert "Insidious (2010)" in msg
        assert "(2)" in msg


class TestAnswer:
    @staticmethod
    def test_answer_lists_films_via_session() -> None:
        rows = [("Saw", date(2004, 10, 29)), ("Insidious", date(2010, 9, 13))]
        result = MagicMock()
        result.all.return_value = rows
        session = MagicMock()
        session.execute.return_value = result
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        service = FilmographyService(session_factory=lambda: session)
        answer = service.answer("Films réalisés par James Wan")

        assert "Saw (2004)" in answer
        assert "Insidious (2010)" in answer

    @staticmethod
    def test_answer_no_name_asks_clarification() -> None:
        service = FilmographyService(session_factory=lambda: MagicMock())
        answer = service.answer("Recommande un slasher")
        assert "précise" in answer.lower()
