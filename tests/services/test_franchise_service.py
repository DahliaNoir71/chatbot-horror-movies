"""Unit tests for FranchiseService: franchise matching, formatting, lookup."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.services.franchise.franchise_service import FranchiseService


class TestMatchFranchise:
    @staticmethod
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            # Typo on "saga" ("sage") must not break recognition.
            ("il y a combien de films dans la sage vendredi 13", "Vendredi 13"),
            ("combien de films dans la saga Scream", "Scream"),
            ("la franchise Friday the 13th", "Vendredi 13"),
            # Accents are stripped before matching.
            ("Massacre à la tronçonneuse", "Massacre à la tronçonneuse"),
        ],
    )
    def test_recognizes_known_franchise(message, expected) -> None:
        match = FranchiseService._match_franchise(message)
        assert match is not None
        assert match[0] == expected

    @staticmethod
    @pytest.mark.parametrize(
        "message",
        [
            "quel saga compte le plus grand nombre de films",  # ranking, not a lookup
            "Recommande un slasher",  # no franchise at all
        ],
    )
    def test_unknown_returns_none(message) -> None:
        assert FranchiseService._match_franchise(message) is None


class TestFormat:
    @staticmethod
    def test_empty_films_notes_absence() -> None:
        msg = FranchiseService._format("Saw", [])
        assert "Saw" in msg
        assert "aucun" in msg.lower()

    @staticmethod
    def test_lists_films_with_count_and_caveat() -> None:
        msg = FranchiseService._format("Saw", [("Saw", 2004), ("Saw II", 2005)])
        assert "Saw (2004)" in msg
        assert "Saw II (2005)" in msg
        assert "2 films" in msg
        assert "approximatif" in msg.lower()


class TestAnswer:
    @staticmethod
    def test_answer_lists_films_via_session() -> None:
        rows = [
            ("Friday the 13th", date(1980, 5, 9)),
            ("Friday the 13th Part 2", date(1981, 4, 30)),
        ]
        result = MagicMock()
        result.all.return_value = rows
        session = MagicMock()
        session.execute.return_value = result
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        service = FranchiseService(session_factory=lambda: session)
        answer = service.answer("Combien de films dans la saga Friday the 13th ?")

        assert "Vendredi 13" in answer
        assert "Friday the 13th (1980)" in answer
        assert "2 films" in answer

    @staticmethod
    def test_answer_unknown_franchise_is_honest() -> None:
        service = FranchiseService(session_factory=lambda: MagicMock())
        answer = service.answer("quel saga compte le plus grand nombre de films")
        assert "saga" in answer.lower()
        assert "Vendredi 13" in answer
