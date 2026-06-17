"""Structured franchise/saga counting from the relational DB.

Answers "how many films are in the X saga" via a direct SQL query on the
``films`` title columns, bypassing the vector RAG path whose ``top_k`` cap
truncates a saga to 5 titles.

The corpus has no franchise/collection metadata (TMDB ``belongs_to_collection``
is not ingested) and stores English titles only (``title_fr`` /
``alternative_titles`` are empty for franchise rows). So instead of extracting a
saga name positionally (brittle: typos, word order, non-lookup questions), the
query is scanned for any *known* franchise — a curated FR/EN alias table. The
English title fragment then drives the SQL match; a vote-count floor drops
fan-films and parodies. Unknown sagas get an honest "not recognized" answer.
"""

import unicodedata
from collections.abc import Callable
from contextlib import AbstractContextManager
from functools import lru_cache

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.database.connection import get_database
from src.database.models.tmdb import Film
from src.etl.utils.logger import setup_logger

logger = setup_logger("services.franchise")

# Max films listed for a single saga answer (no vector top_k cap here).
_FRANCHISE_LIMIT = 30

# Vote-count floor below which a title match is treated as a fan-film/parody.
# Heuristic substitute for the absent TMDB collection metadata. Calibrated on
# the corpus: official saga entries carry 1000+ votes, fan uploads/parodies
# carry <=20, so 50 separates them with margin without dropping a real film.
_MIN_VOTE_COUNT = 50

# Known horror franchises: canonical FR display name -> title fragments (FR and
# EN), accent-stripped lowercase. A fragment found in the query identifies the
# franchise (robust to typos in "saga"/word order); the same fragments drive the
# SQL ILIKE (the FR ones harmlessly match nothing since titles are English, the
# EN ones match). Extend this table to cover more sagas.
_KNOWN_FRANCHISES: dict[str, tuple[str, ...]] = {
    "Vendredi 13": ("vendredi 13", "friday the 13th"),
    "Halloween": ("halloween",),
    "Scream": ("scream",),
    "Saw": ("saw",),
    "Les Griffes de la nuit": ("griffes de la nuit", "freddy", "nightmare on elm street"),
    "Massacre à la tronçonneuse": ("tronconneuse", "texas chain"),
    "Souviens-toi l'été dernier": ("souviens-toi", "i know what you did"),
    "Destination finale": ("destination finale", "final destination"),
    "Chucky": ("chucky", "jeu d'enfant", "child's play"),
    "La Nonne": ("la nonne", "the nun"),
    "L'Exorciste": ("exorciste", "exorcist"),
    "Conjuring": ("conjuring", "dossiers warren"),
    "Insidious": ("insidious",),
    "Paranormal Activity": ("paranormal activity",),
    "Annabelle": ("annabelle",),
    "Hellraiser": ("hellraiser",),
    "Evil Dead": ("evil dead",),
}

# Honest fallback when no known franchise is mentioned: covers typos on the saga
# name, unknown franchises, and ranking questions ("which saga is biggest") that
# cannot be answered without collection metadata.
_UNKNOWN_MESSAGE = (
    "Je ne reconnais pas de saga précise dans ta question. Je sais compter les films des "
    "grandes franchises d'horreur de ma base (Vendredi 13, Halloween, Scream, Saw, Les "
    "Griffes de la nuit, Destination finale, Conjuring…) — reformule avec le nom de la saga. "
    "En revanche je ne peux pas classer les sagas entre elles : ma base n'a pas de "
    "métadonnées de collection."
)


def _session_factory_default() -> AbstractContextManager[Session]:
    """Return a sync session context manager bound to the relational engine."""
    return get_database().session()


def _strip_accents(text: str) -> str:
    """Return ``text`` with combining diacritics removed (for alias matching)."""
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )


class FranchiseService:
    """Answers franchise/saga counting questions from the relational DB."""

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
        """Build a saga-count answer for the given user message.

        Args:
            user_message: Raw user query (e.g. "combien de films dans la saga Saw").

        Returns:
            A French count and listing of matching films, or an honest fallback
            when no known franchise is recognized.
        """
        match = self._match_franchise(user_message)
        if match is None:
            self._logger.info("Franchise not recognized: %s", user_message[:80])
            return _UNKNOWN_MESSAGE
        display, fragments = match
        films = self._lookup(fragments)
        self._logger.info("Franchise lookup: saga=%s, films=%d", display, len(films))
        return self._format(display, films)

    @staticmethod
    def _match_franchise(query: str) -> tuple[str, tuple[str, ...]] | None:
        """Identify a known franchise mentioned anywhere in the query.

        Scanning for known names (rather than extracting positionally) is robust
        to typos on "saga", word order and filler words.

        Args:
            query: Raw user query.

        Returns:
            ``(display_name, title_fragments)`` for the first matching franchise,
            or None when none is recognized.
        """
        normalized = _strip_accents(query).lower()
        for display, fragments in _KNOWN_FRANCHISES.items():
            if any(fragment in normalized for fragment in fragments):
                return display, fragments
        return None

    def _lookup(self, fragments: tuple[str, ...]) -> list[tuple[str, int | None]]:
        """Query films whose title matches any franchise fragment, by date.

        Matches the EN ``title`` and ``original_title`` (the corpus is
        English-titled); the vote-count floor excludes fan-films and parodies
        sharing the saga name.

        Args:
            fragments: Title fragments identifying the franchise.

        Returns:
            List of ``(title, year)`` tuples in chronological order.
        """
        conditions = []
        for fragment in fragments:
            like = f"%{fragment}%"
            conditions.append(Film.title.ilike(like))
            conditions.append(Film.original_title.ilike(like))
        stmt = (
            select(Film.title, Film.release_date)
            .where(or_(*conditions))
            .where(Film.vote_count >= _MIN_VOTE_COUNT)
            .order_by(Film.release_date)
            .limit(_FRANCHISE_LIMIT)
        )
        with self._session_factory() as session:
            rows = session.execute(stmt).all()
        return [(row[0], row[1].year if row[1] else None) for row in rows]

    @staticmethod
    def _format(name: str, films: list[tuple[str, int | None]]) -> str:
        """Format the count and listing (or an empty-result note) in French.

        The wording stays explicitly approximate: without collection metadata
        the count reflects only DB entries above the vote floor.

        Args:
            name: Canonical franchise display name.
            films: ``(title, year)`` tuples to list.

        Returns:
            A user-facing French sentence.
        """
        if not films:
            return (
                f"Je connais la saga « {name} » mais je n'ai trouvé aucun de ses films "
                "dans ma base."
            )
        listing = ", ".join(f"{title} ({year})" if year else title for title, year in films)
        return (
            f"D'après ma base, la saga « {name} » compte au moins {len(films)} films : {listing}. "
            "Ce décompte est approximatif : je me limite aux entrées les plus connues de ma base "
            "et certaines suites ou spin-offs mineurs peuvent manquer."
        )


@lru_cache(maxsize=1)
def get_franchise_service() -> FranchiseService:
    """Get the singleton FranchiseService instance."""
    return FranchiseService()
