"""Structured filmography lookup for director / actor questions.

Answers "films directed by X" / "films with actor X" via a direct SQL query on
the denormalized ``films.director`` and ``films.cast_names`` columns, bypassing
the vector RAG path whose top_k cap truncates filmographies longer than 5 films.
"""

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from functools import lru_cache

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.database.connection import get_database
from src.database.models.tmdb import Film
from src.etl.utils.logger import setup_logger

logger = setup_logger("services.filmography")

# Max films listed for a single filmography answer (no vector top_k cap here).
_FILMOGRAPHY_LIMIT = 25

# Triggers after which the trailing text is taken as the person name. "de"/"d'"
# match lowercase only so name particles ("De Niro", "Del Toro") are preserved.
_TRIGGER_PATTERN = re.compile(
    r"(?i:r[eé]alis[eé]s?\s+par|filmographie|\bpar\b|\bavec\b|\bjoue\b)|\bde\b|\bd'"
)
_STRIP_CHARS = " \t?.!,;:'\"’«»"
_LEADING_FILLER = re.compile(r"^(?:dans\s+|les?\s+|l'|the\s+)", re.IGNORECASE)


def _session_factory_default() -> AbstractContextManager[Session]:
    """Return a sync session context manager bound to the relational engine."""
    return get_database().session()


class FilmographyService:
    """Answers director/actor filmography questions from the relational DB."""

    def __init__(
        self,
        session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
    ) -> None:
        """Initialize with an injectable session factory.

        Args:
            session_factory: Callable yielding a sync DB session context manager
                (overridable for tests). Defaults to the relational engine.
        """
        self._session_factory = session_factory or _session_factory_default
        self._logger = logger

    def answer(self, user_message: str) -> str:
        """Build a filmography answer for the given user message.

        Args:
            user_message: Raw user query (e.g. "films réalisés par James Wan").

        Returns:
            A French listing of matching films, or a graceful fallback.
        """
        name = self._extract_name(user_message)
        if not name:
            return (
                "Pour une filmographie, précise un nom : "
                "« films réalisés par … » ou « films avec … »."
            )
        role = self._extract_role(user_message)
        films = self._lookup(name, role)
        self._logger.info("Filmography lookup: name=%s, role=%s, films=%d", name, role, len(films))
        return self._format(name, films)

    def _lookup(self, name: str, role: str) -> list[tuple[str, int | None]]:
        """Query films credited to a person, by popularity.

        Args:
            name: Person name extracted from the query.
            role: Credit filter — ``"director"`` (réalisés par), ``"cast"``
                (avec/joue) or ``"both"`` (ambiguous trigger). Keeps an acting
                cameo (e.g. Cronenberg in "Ready or Not") from polluting — and,
                via the popularity sort, topping — a "directed by" answer.

        Returns:
            List of ``(title, year)`` tuples.
        """
        director = Film.director.ilike(f"%{name}%")
        cast = Film.cast_names.any(name)
        if role == "director":
            condition = director
        elif role == "cast":
            condition = cast
        else:
            condition = or_(director, cast)
        stmt = (
            select(Film.title, Film.release_date)
            .where(condition)
            .order_by(Film.popularity.desc())
            .limit(_FILMOGRAPHY_LIMIT)
        )
        with self._session_factory() as session:
            rows = session.execute(stmt).all()
        return [(row[0], row[1].year if row[1] else None) for row in rows]

    @staticmethod
    def _extract_name(message: str) -> str | None:
        """Extract the trailing person name after the last filmography trigger.

        Args:
            message: Raw user query.

        Returns:
            The extracted name, or None when no trigger is present.
        """
        matches = list(_TRIGGER_PATTERN.finditer(message))
        if not matches:
            return None
        tail = message[matches[-1].end() :].strip(_STRIP_CHARS)
        tail = _LEADING_FILLER.sub("", tail).strip()
        return tail or None

    @staticmethod
    def _extract_role(message: str) -> str:
        """Classify the credit filter implied by the last filmography trigger.

        "réalisés par" → ``"director"``; "avec"/"joue" → ``"cast"``; anything
        else (filmographie, de, par) stays inclusive (``"both"``).

        Args:
            message: Raw user query.

        Returns:
            One of ``"director"``, ``"cast"`` or ``"both"``.
        """
        matches = list(_TRIGGER_PATTERN.finditer(message))
        trigger = matches[-1].group(0).lower() if matches else ""
        if "alis" in trigger:
            return "director"
        if "avec" in trigger or "joue" in trigger:
            return "cast"
        return "both"

    @staticmethod
    def _format(name: str, films: list[tuple[str, int | None]]) -> str:
        """Format the film list (or an empty-result message) in French.

        Args:
            name: Person name used in the message.
            films: ``(title, year)`` tuples to list.

        Returns:
            A user-facing French sentence.
        """
        if not films:
            return f"Je n'ai trouvé aucun film d'horreur de {name} dans ma base."
        listing = ", ".join(f"{title} ({year})" if year else title for title, year in films)
        return f"Films d'horreur de {name} dans ma base ({len(films)}) : {listing}."


@lru_cache(maxsize=1)
def get_filmography_service() -> FilmographyService:
    """Get the singleton FilmographyService instance."""
    return FilmographyService()
