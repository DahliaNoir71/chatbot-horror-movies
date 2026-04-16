"""Unit tests for AggregatedFilm.rag_text bilingual generation."""

from __future__ import annotations

from datetime import date

from src.etl.aggregation.schemas import AggregatedFilm


def _make_film(**overrides: object) -> AggregatedFilm:
    data: dict[str, object] = {
        "tmdb_id": 9552,
        "title": "The Exorcist",
        "title_fr": "L'Exorciste",
        "overview": "A mother seeks help.",
        "overview_fr": "Une mère cherche de l'aide.",
        "alternative_titles": ["L'Exorciste : Version Intégrale"],
        "tagline": "Something beyond comprehension.",
        "director": "William Friedkin",
        "cast": ["Ellen Burstyn", "Linda Blair"],
        "keywords": ["possession", "exorcism"],
        "release_date": date(1973, 12, 26),
    }
    data.update(overrides)
    return AggregatedFilm(**data)  # type: ignore[arg-type]


class TestRagTextBilingual:
    """AggregatedFilm.rag_text — bilingual FR/EN embedding text."""

    @staticmethod
    def test_rag_text_bilingual_format() -> None:
        text = _make_film().rag_text
        assert "The Exorcist / L'Exorciste" in text
        assert "A mother seeks help." in text
        assert "Une mère cherche de l'aide." in text
        assert "Alternative titles: L'Exorciste : Version Intégrale" in text
        assert "Director: William Friedkin" in text
        assert "Cast: Ellen Burstyn, Linda Blair" in text
        assert "Keywords: possession, exorcism" in text

    @staticmethod
    def test_rag_text_skips_duplicates() -> None:
        """title == title_fr must not render '... / ...' and FR overview same as EN not duplicated."""
        text = _make_film(
            title="Saw",
            title_fr="Saw",
            overview="Duplicated text",
            overview_fr="Duplicated text",
        ).rag_text
        assert "Saw / Saw" not in text
        assert text.count("Duplicated text") == 1

    @staticmethod
    def test_rag_text_empty_optionals() -> None:
        """Minimal film: only title + defaults — no optional sections rendered."""
        minimal = AggregatedFilm(tmdb_id=1, title="Barebones")  # type: ignore[arg-type]
        text = minimal.rag_text
        assert text == "Barebones"
        assert "Director:" not in text
        assert "Cast:" not in text
        assert "Keywords:" not in text
        assert "Alternative titles:" not in text
        assert " / " not in text
