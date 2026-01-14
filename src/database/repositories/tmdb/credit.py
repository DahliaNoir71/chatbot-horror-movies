"""Credit repository for cast and crew operations.

Provides CRUD and query operations for film credits
including directors, actors, writers, and producers.
"""

from typing import TypedDict

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.tmdb import Credit
from src.database.repositories.base import BaseRepository


class CreditData(TypedDict, total=False):
    """Typed dictionary for credit input data."""

    film_id: int
    person_name: str
    role_type: str
    character_name: str | None
    display_order: int


class CreditRepository(BaseRepository[Credit]):
    """Repository for Credit entity operations.

    Credits link persons (directors, actors, etc.) to films.
    """

    model = Credit

    def __init__(self, session: Session) -> None:
        """Initialize credit repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_film(self, film_id: int) -> list[Credit]:
        """Get all credits for a film.

        Args:
            film_id: Film primary key.

        Returns:
            List of credits ordered by display_order.
        """
        stmt = select(Credit).where(Credit.film_id == film_id).order_by(Credit.display_order)
        return list(self._session.scalars(stmt).all())

    def get_by_film_and_role(self, film_id: int, role_type: str) -> list[Credit]:
        """Get credits for a film filtered by role type.

        Args:
            film_id: Film primary key.
            role_type: One of 'director', 'actor', 'writer', 'producer'.

        Returns:
            List of credits for that role.
        """
        stmt = (
            select(Credit)
            .where(Credit.film_id == film_id, Credit.role_type == role_type)
            .order_by(Credit.display_order)
        )
        return list(self._session.scalars(stmt).all())

    def get_directors(self, film_id: int) -> list[Credit]:
        """Get directors for a film.

        Args:
            film_id: Film primary key.

        Returns:
            List of director credits.
        """
        return self.get_by_film_and_role(film_id, "director")

    def get_actors(self, film_id: int, limit: int = 10) -> list[Credit]:
        """Get top billed actors for a film.

        Args:
            film_id: Film primary key.
            limit: Maximum number of actors.

        Returns:
            List of actor credits ordered by billing.
        """
        stmt = (
            select(Credit)
            .where(Credit.film_id == film_id, Credit.role_type == "actor")
            .order_by(Credit.display_order)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_by_person_name(self, name: str, limit: int = 50) -> list[Credit]:
        """Search credits by person name.

        Args:
            name: Person name to search.
            limit: Maximum results.

        Returns:
            List of matching credits.
        """
        stmt = (
            select(Credit)
            .where(Credit.person_name.ilike(f"%{name}%"))
            .order_by(Credit.person_name)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_films_by_director(self, director_name: str) -> list[int]:
        """Get film IDs directed by a person.

        Args:
            director_name: Director name (exact match).

        Returns:
            List of film IDs.
        """
        stmt = select(Credit.film_id).where(
            Credit.person_name == director_name,
            Credit.role_type == "director",
        )
        return list(self._session.scalars(stmt).all())

    def delete_by_film(self, film_id: int) -> int:
        """Delete all credits for a film.

        Args:
            film_id: Film primary key.

        Returns:
            Number of credits deleted.
        """
        stmt = delete(Credit).where(Credit.film_id == film_id)
        result = self._session.execute(stmt)
        self._session.flush()
        return result.rowcount

    def bulk_insert(self, credits_data: list[CreditData]) -> int:
        """Bulk insert credits for a film.

        Args:
            credits_data: List of credit dictionaries.

        Returns:
            Number of credits inserted.
        """
        if not credits_data:
            return 0

        stmt = insert(Credit).values(credits_data)
        stmt = stmt.on_conflict_do_nothing()
        self._session.execute(stmt)
        self._session.flush()
        return len(credits_data)

    def replace_for_film(self, film_id: int, credits_data: list[CreditData]) -> int:
        """Replace all credits for a film.

        Deletes existing credits and inserts new ones.

        Args:
            film_id: Film primary key.
            credits_data: New credit data (without film_id).

        Returns:
            Number of credits inserted.
        """
        self.delete_by_film(film_id)

        if not credits_data:
            return 0

        for credit in credits_data:
            credit["film_id"] = film_id

        return self.bulk_insert(credits_data)

    def count_by_role(self) -> dict[str, int]:
        """Count credits by role type.

        Returns:
            Dictionary mapping role_type to count.
        """
        stmt = select(Credit.role_type, func.count(Credit.id)).group_by(Credit.role_type)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def get_prolific_directors(self, min_films: int = 3) -> list[tuple[str, int]]:
        """Get directors with multiple films.

        Args:
            min_films: Minimum number of films.

        Returns:
            List of (director_name, film_count) tuples.
        """
        stmt = (
            select(Credit.person_name, func.count(Credit.film_id).label("count"))
            .where(Credit.role_type == "director")
            .group_by(Credit.person_name)
            .having(func.count(Credit.film_id) >= min_films)
            .order_by(func.count(Credit.film_id).desc())
        )
        result = self._session.execute(stmt).all()
        return [(row[0], row[1]) for row in result]
