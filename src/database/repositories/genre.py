"""Genre repository for reference data operations.

Provides CRUD and lookup operations for film genres.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.film import Genre
from src.database.repositories.base import BaseRepository


class GenreRepository(BaseRepository[Genre]):
    """Repository for Genre entity operations.

    Genres are reference data, typically seeded once
    and looked up frequently during ETL.
    """

    model = Genre

    def __init__(self, session: Session) -> None:
        """Initialize genre repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_tmdb_id(self, tmdb_genre_id: int) -> Genre | None:
        """Retrieve genre by TMDB identifier.

        Args:
            tmdb_genre_id: TMDB genre ID.

        Returns:
            Genre instance or None.
        """
        return self.get_by_field("tmdb_genre_id", tmdb_genre_id)

    def get_by_name(self, name: str) -> Genre | None:
        """Retrieve genre by name.

        Args:
            name: Genre name (e.g., 'Horror').

        Returns:
            Genre instance or None.
        """
        return self.get_by_field("name", name)

    def get_or_create(self, tmdb_genre_id: int, name: str) -> Genre:
        """Get existing genre or create new one.

        Args:
            tmdb_genre_id: TMDB genre ID.
            name: Genre display name.

        Returns:
            Genre instance (existing or newly created).
        """
        existing = self.get_by_tmdb_id(tmdb_genre_id)
        if existing:
            return existing

        genre = Genre(tmdb_genre_id=tmdb_genre_id, name=name)
        return self.create(genre)

    def get_id_map(self) -> dict[int, int]:
        """Get mapping of TMDB genre IDs to internal IDs.

        Returns:
            Dictionary mapping tmdb_genre_id to id.
        """
        stmt = select(Genre.tmdb_genre_id, Genre.id)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def bulk_upsert(self, genres_data: list[dict[str, int | str]]) -> int:
        """Bulk insert or update genres.

        Args:
            genres_data: List of dicts with tmdb_genre_id and name.

        Returns:
            Number of genres processed.
        """
        if not genres_data:
            return 0

        stmt = insert(Genre).values(genres_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_genre_id"],
            set_={"name": stmt.excluded.name},
        )
        self._session.execute(stmt)
        self._session.flush()
        return len(genres_data)

    def get_all_sorted(self) -> list[Genre]:
        """Get all genres sorted alphabetically.

        Returns:
            List of all genres.
        """
        stmt = select(Genre).order_by(Genre.name)
        return list(self._session.scalars(stmt).all())
