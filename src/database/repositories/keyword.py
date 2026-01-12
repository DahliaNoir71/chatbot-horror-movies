"""Keyword repository for semantic tagging operations.

Provides CRUD and lookup operations for film keywords
used in RAG semantic search.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.film import Keyword
from src.database.repositories.base import BaseRepository


class KeywordRepository(BaseRepository[Keyword]):
    """Repository for Keyword entity operations.

    Keywords are semantic tags like 'slasher', 'found-footage',
    'zombie' used for RAG search enhancement.
    """

    model = Keyword

    def __init__(self, session: Session) -> None:
        """Initialize keyword repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_tmdb_id(self, tmdb_keyword_id: int) -> Keyword | None:
        """Retrieve keyword by TMDB identifier.

        Args:
            tmdb_keyword_id: TMDB keyword ID.

        Returns:
            Keyword instance or None.
        """
        return self.get_by_field("tmdb_keyword_id", tmdb_keyword_id)

    def get_by_name(self, name: str) -> Keyword | None:
        """Retrieve keyword by name (case-insensitive).

        Args:
            name: Keyword text.

        Returns:
            Keyword instance or None.
        """
        stmt = select(Keyword).where(Keyword.name.ilike(name))
        return self._session.scalars(stmt).first()

    def get_or_create(
        self,
        name: str,
        tmdb_keyword_id: int | None = None,
    ) -> Keyword:
        """Get existing keyword or create new one.

        Args:
            name: Keyword text.
            tmdb_keyword_id: Optional TMDB keyword ID.

        Returns:
            Keyword instance (existing or newly created).
        """
        # First try by TMDB ID if provided
        if tmdb_keyword_id:
            existing = self.get_by_tmdb_id(tmdb_keyword_id)
            if existing:
                return existing

        # Then try by name
        existing = self.get_by_name(name)
        if existing:
            return existing

        # Create new
        keyword = Keyword(name=name, tmdb_keyword_id=tmdb_keyword_id)
        return self.create(keyword)

    def get_id_map(self) -> dict[int, int]:
        """Get mapping of TMDB keyword IDs to internal IDs.

        Returns:
            Dictionary mapping tmdb_keyword_id to id.
        """
        stmt = select(Keyword.tmdb_keyword_id, Keyword.id).where(
            Keyword.tmdb_keyword_id != None  # noqa: E711
        )
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def get_name_map(self) -> dict[str, int]:
        """Get mapping of keyword names to internal IDs.

        Returns:
            Dictionary mapping lowercase name to id.
        """
        stmt = select(Keyword.name, Keyword.id)
        result = self._session.execute(stmt).all()
        return {row[0].lower(): row[1] for row in result}

    def search(self, query: str, limit: int = 20) -> list[Keyword]:
        """Search keywords by name prefix.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            List of matching keywords.
        """
        stmt = (
            select(Keyword)
            .where(Keyword.name.ilike(f"%{query}%"))
            .order_by(Keyword.name)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def bulk_upsert(self, keywords_data: list[dict[str, int | str | None]]) -> int:
        """Bulk insert or update keywords.

        Args:
            keywords_data: List of dicts with name and optional tmdb_keyword_id.

        Returns:
            Number of keywords processed.
        """
        if not keywords_data:
            return 0

        stmt = insert(Keyword).values(keywords_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        self._session.execute(stmt)
        self._session.flush()
        return len(keywords_data)

    def get_popular(self, limit: int = 50) -> list[tuple[Keyword, int]]:
        """Get most used keywords with film count.

        Args:
            limit: Maximum results.

        Returns:
            List of (Keyword, count) tuples.
        """
        from sqlalchemy import func

        from src.database.models.film import FilmKeyword

        stmt = (
            select(Keyword, func.count(FilmKeyword.film_id).label("count"))
            .join(FilmKeyword)
            .group_by(Keyword.id)
            .order_by(func.count(FilmKeyword.film_id).desc())
            .limit(limit)
        )
        result = self._session.execute(stmt).all()
        return [(row[0], row[1]) for row in result]
