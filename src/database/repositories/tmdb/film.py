"""Film repository with specialized query methods.

Provides CRUD operations and specialized queries for
film entities including bulk upsert for ETL pipelines.
"""

from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from src.database.models.tmdb import Film, FilmGenre, FilmKeyword
from src.database.repositories.base import BaseRepository


class FilmRepository(BaseRepository[Film]):
    """Repository for Film entity operations.

    Provides methods for querying films by various criteria
    and bulk operations for ETL pipelines.
    """

    model = Film

    def __init__(self, session: Session) -> None:
        """Initialize film repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_tmdb_id(self, tmdb_id: int) -> Film | None:
        """Retrieve film by TMDB identifier.

        Args:
            tmdb_id: TMDB movie ID.

        Returns:
            Film instance or None.
        """
        return self.get_by_field("tmdb_id", tmdb_id)

    def get_by_imdb_id(self, imdb_id: str) -> Film | None:
        """Retrieve film by IMDb identifier.

        Args:
            imdb_id: IMDb ID (e.g., 'tt1234567').

        Returns:
            Film instance or None.
        """
        return self.get_by_field("imdb_id", imdb_id)

    def get_with_relations(self, film_id: int) -> Film | None:
        """Retrieve film with all related entities loaded.

        Args:
            film_id: Primary key.

        Returns:
            Film with genres, keywords, credits, rt_score loaded.
        """
        stmt = (
            select(Film)
            .options(
                joinedload(Film.genres),
                joinedload(Film.keywords),
                joinedload(Film.credits),
                joinedload(Film.rt_score),
            )
            .where(Film.id == film_id)
        )
        return self._session.scalars(stmt).unique().first()

    def get_tmdb_ids(self) -> set[int]:
        """Get all existing TMDB IDs.

        Returns:
            Set of TMDB IDs in database.
        """
        stmt = select(Film.tmdb_id)
        return set(self._session.scalars(stmt).all())

    def search_by_title(self, query: str, limit: int = 20) -> list[Film]:
        """Search films by title using trigram similarity.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            List of matching films ordered by similarity.
        """
        stmt = (
            select(Film)
            .where(Film.title.ilike(f"%{query}%"))
            .order_by(Film.popularity.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_by_year(self, year: int, limit: int = 100) -> list[Film]:
        """Get films released in a specific year.

        Args:
            year: Release year.
            limit: Maximum results.

        Returns:
            List of films from that year.
        """
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        stmt = (
            select(Film)
            .where(Film.release_date.between(start_date, end_date))
            .order_by(Film.popularity.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_by_genre_id(self, genre_id: int, limit: int = 100) -> list[Film]:
        """Get films by genre.

        Args:
            genre_id: Genre primary key.
            limit: Maximum results.

        Returns:
            List of films with that genre.
        """
        stmt = (
            select(Film)
            .join(FilmGenre)
            .where(FilmGenre.genre_id == genre_id)
            .order_by(Film.popularity.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_top_rated(self, min_votes: int = 100, limit: int = 50) -> list[Film]:
        """Get top rated films with minimum vote threshold.

        Args:
            min_votes: Minimum vote count required.
            limit: Maximum results.

        Returns:
            List of top rated films.
        """
        stmt = (
            select(Film)
            .where(Film.vote_count >= min_votes)
            .order_by(Film.vote_average.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_without_rt_scores(self, limit: int = 100) -> list[Film]:
        """Get films missing Rotten Tomatoes data.

        Args:
            limit: Maximum results.

        Returns:
            List of films without RT scores.
        """
        stmt = (
            select(Film)
            .outerjoin(Film.rt_score)
            .where(Film.rt_score == None)  # noqa: E711
            .order_by(Film.popularity.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_without_embeddings(self, limit: int = 100) -> list[Film]:
        """Get films missing vector embeddings.

        Args:
            limit: Maximum results.

        Returns:
            List of films without embeddings.
        """
        stmt = (
            select(Film)
            .where(Film.embedding == None)  # noqa: E711
            .order_by(Film.popularity.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def upsert(self, data: dict[str, Any]) -> Film:
        """Insert or update a single film.

        Args:
            data: Film data dictionary with tmdb_id as key.

        Returns:
            Upserted film instance.
        """
        stmt = (
            insert(Film)
            .values(**data)
            .on_conflict_do_update(
                index_elements=["tmdb_id"],
                set_={k: v for k, v in data.items() if k != "tmdb_id"},
            )
            .returning(Film)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.scalar_one()

    def bulk_upsert(self, films_data: list[dict[str, Any]]) -> int:
        """Bulk insert or update films.

        Uses PostgreSQL ON CONFLICT for efficient upsert.

        Args:
            films_data: List of film data dictionaries.

        Returns:
            Number of films processed.
        """
        if not films_data:
            return 0

        stmt = insert(Film).values(films_data)
        update_cols = {col.name: col for col in stmt.excluded if col.name not in ("id", "tmdb_id")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_id"],
            set_=update_cols,
        )
        self._session.execute(stmt)
        self._session.flush()
        return len(films_data)

    def update_embedding(self, film_id: int, embedding: list[float]) -> None:
        """Update film embedding vector.

        Args:
            film_id: Film primary key.
            embedding: Vector embedding.
        """
        stmt = update(Film).where(Film.id == film_id).values(embedding=embedding)
        self._session.execute(stmt)
        self._session.flush()

    def add_genre(self, film_id: int, genre_id: int) -> None:
        """Associate a genre with a film.

        Args:
            film_id: Film primary key.
            genre_id: Genre primary key.
        """
        stmt = insert(FilmGenre).values(film_id=film_id, genre_id=genre_id).on_conflict_do_nothing()
        self._session.execute(stmt)

    def add_keyword(self, film_id: int, keyword_id: int, source: str = "tmdb") -> None:
        """Associate a keyword with a film.

        Args:
            film_id: Film primary key.
            keyword_id: Keyword primary key.
            source: Data source identifier.
        """
        stmt = (
            insert(FilmKeyword)
            .values(film_id=film_id, keyword_id=keyword_id, source=source)
            .on_conflict_do_nothing()
        )
        self._session.execute(stmt)

    def count_by_source(self) -> dict[str, int]:
        """Count films grouped by source.

        Returns:
            Dictionary mapping source to count.
        """
        stmt = select(Film.source, func.count(Film.id)).group_by(Film.source)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def get_stats(self) -> dict[str, Any]:
        """Get film collection statistics.

        Returns:
            Dictionary with various stats.
        """
        total = self.count()
        with_embeddings = self._session.scalar(
            select(func.count(Film.id)).where(Film.embedding != None)  # noqa: E711
        )
        avg_rating = self._session.scalar(select(func.avg(Film.vote_average)))
        by_source = self.count_by_source()

        return {
            "total": total,
            "with_embeddings": with_embeddings or 0,
            "without_embeddings": total - (with_embeddings or 0),
            "average_rating": round(float(avg_rating or 0), 2),
            "by_source": by_source,
        }
