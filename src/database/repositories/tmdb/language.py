"""Spoken language repository.

Provides CRUD and lookup operations for spoken
languages (ISO 639-1 language codes).
"""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.tmdb import FilmLanguage, SpokenLanguage
from src.database.repositories.base import BaseRepository


class SpokenLanguageData(TypedDict):
    """Typed dictionary for spoken language input data."""

    iso_639_1: str
    name: str


class SpokenLanguageRepository(BaseRepository[SpokenLanguage]):
    """Repository for SpokenLanguage entity operations.

    Spoken languages are ISO 639-1 language codes.
    """

    model = SpokenLanguage

    def __init__(self, session: Session) -> None:
        """Initialize spoken language repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_iso(self, iso_639_1: str) -> SpokenLanguage | None:
        """Retrieve language by ISO code.

        Args:
            iso_639_1: ISO 639-1 language code.

        Returns:
            SpokenLanguage instance or None.
        """
        return self.get_by_field("iso_639_1", iso_639_1)

    def get_or_create(self, iso_639_1: str, name: str) -> SpokenLanguage:
        """Get existing language or create new one.

        Args:
            iso_639_1: ISO 639-1 code.
            name: Language name in English.

        Returns:
            SpokenLanguage instance.
        """
        existing = self.get_by_iso(iso_639_1)
        if existing:
            return existing

        language = SpokenLanguage(iso_639_1=iso_639_1, name=name)
        return self.create(language)

    def get_id_map(self) -> dict[str, int]:
        """Get mapping of ISO codes to internal IDs.

        Returns:
            Dictionary mapping iso_639_1 to id.
        """
        stmt = select(SpokenLanguage.iso_639_1, SpokenLanguage.id)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def bulk_upsert(self, languages_data: list[SpokenLanguageData]) -> int:
        """Bulk insert or update languages.

        Args:
            languages_data: List of language dictionaries.

        Returns:
            Number of languages processed.
        """
        if not languages_data:
            return 0

        stmt = insert(SpokenLanguage).values(languages_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["iso_639_1"],
            set_={"name": stmt.excluded.name},
        )
        self._session.execute(stmt)
        self._session.flush()
        return len(languages_data)

    def add_to_film(self, film_id: int, language_id: int) -> None:
        """Associate language with a film.

        Args:
            film_id: Film primary key.
            language_id: Language primary key.
        """
        stmt = (
            insert(FilmLanguage)
            .values(film_id=film_id, language_id=language_id)
            .on_conflict_do_nothing()
        )
        self._session.execute(stmt)

    def get_all_sorted(self) -> list[SpokenLanguage]:
        """Get all languages sorted by name.

        Returns:
            List of all languages.
        """
        stmt = select(SpokenLanguage).order_by(SpokenLanguage.name)
        return list(self._session.scalars(stmt).all())
