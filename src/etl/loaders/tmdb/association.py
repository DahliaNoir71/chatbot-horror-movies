"""TMDB association data loader.

Handles film junction tables: film_genres, film_keywords,
film_companies, film_languages.
"""

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models import FilmCompany, FilmGenre, FilmKeyword, FilmLanguage
from src.etl.loaders.base import BaseLoader, LoaderStats

if TYPE_CHECKING:
    from src.etl.loaders.tmdb.reference import ReferenceLoader


class AssociationLoader(BaseLoader):
    """Loader for film association tables.

    Handles film_genres, film_keywords, film_companies, film_languages.
    Each load replaces existing associations for the given film.
    """

    name = "tmdb.association"

    def __init__(self, session: Session, ref_loader: "ReferenceLoader") -> None:
        """Initialize with session and reference loader.

        Args:
            session: SQLAlchemy session.
            ref_loader: Reference loader for ID mappings.
        """
        super().__init__(session)
        self._ref = ref_loader

    def load(self, data: object) -> LoaderStats:
        """Not used directly. Use specific load_* methods.

        Args:
            data: Unused parameter.

        Raises:
            NotImplementedError: Always raised.
        """
        raise NotImplementedError("Use load_genres, load_keywords, etc.")

    def load_genres(self, film_id: int, tmdb_genre_ids: list[int]) -> None:
        """Load film-genre associations.

        Args:
            film_id: Internal database film ID.
            tmdb_genre_ids: List of TMDB genre IDs.
        """
        self._logger.info(f"Loading {len(tmdb_genre_ids)} genre associations for film_id={film_id}")
        self._delete_associations(FilmGenre, film_id)
        genre_map = self._ref.genre.get_id_map()
        inserted = 0

        for tmdb_id in tmdb_genre_ids:
            genre_id = genre_map.get(tmdb_id)
            if genre_id is not None:
                self._insert_association(FilmGenre, film_id, "genre_id", genre_id)
                inserted += 1

        self._logger.info(f"Genre associations: {inserted} inserted")

    def load_keywords(self, film_id: int, tmdb_keyword_ids: list[int]) -> None:
        """Load film-keyword associations.

        Args:
            film_id: Internal database film ID.
            tmdb_keyword_ids: List of TMDB keyword IDs.
        """
        self._logger.info(
            f"Loading {len(tmdb_keyword_ids)} keyword associations for film_id={film_id}"
        )
        self._delete_associations(FilmKeyword, film_id)
        keyword_map = self._ref.keyword.get_id_map()
        inserted = 0

        for tmdb_id in tmdb_keyword_ids:
            keyword_id = keyword_map.get(tmdb_id)
            if keyword_id is not None:
                self._insert_keyword_association(film_id, keyword_id)
                inserted += 1

        self._logger.info(f"Keyword associations: {inserted} inserted")

    def load_companies(self, film_id: int, tmdb_company_ids: list[int]) -> None:
        """Load film-company associations.

        Args:
            film_id: Internal database film ID.
            tmdb_company_ids: List of TMDB company IDs.
        """
        self._logger.info(
            f"Loading {len(tmdb_company_ids)} company associations for film_id={film_id}"
        )
        self._delete_associations(FilmCompany, film_id)
        company_map = self._ref.company.get_id_map()
        inserted = 0

        for tmdb_id in tmdb_company_ids:
            company_id = company_map.get(tmdb_id)
            if company_id is not None:
                self._insert_association(FilmCompany, film_id, "company_id", company_id)
                inserted += 1

        self._logger.info(f"Company associations: {inserted} inserted")

    def load_languages(self, film_id: int, iso_codes: list[str]) -> None:
        """Load film-language associations.

        Args:
            film_id: Internal database film ID.
            iso_codes: List of ISO 639-1 language codes.
        """
        self._logger.info(f"Loading {len(iso_codes)} language associations for film_id={film_id}")
        self._delete_associations(FilmLanguage, film_id)
        language_map = self._ref.language.get_id_map()
        inserted = 0

        for iso_code in iso_codes:
            language_id = language_map.get(iso_code)
            if language_id is not None:
                self._insert_association(FilmLanguage, film_id, "language_id", language_id)
                inserted += 1

        self._logger.info(f"Language associations: {inserted} inserted")

    def _delete_associations(self, model: type, film_id: int) -> None:
        """Delete existing associations for a film.

        Args:
            model: SQLAlchemy model class.
            film_id: Internal database film ID.
        """
        stmt = delete(model).where(model.film_id == film_id)  # type: ignore[attr-defined]
        self._session.execute(stmt)

    def _insert_association(
        self,
        model: type,
        film_id: int,
        fk_column: str,
        fk_value: int,
    ) -> None:
        """Insert a generic association record.

        Args:
            model: SQLAlchemy model class.
            film_id: Internal database film ID.
            fk_column: Foreign key column name.
            fk_value: Foreign key value.
        """
        stmt = insert(model).values(film_id=film_id, **{fk_column: fk_value})
        stmt = stmt.on_conflict_do_nothing()
        self._session.execute(stmt)

    def _insert_keyword_association(self, film_id: int, keyword_id: int) -> None:
        """Insert film-keyword with source field.

        Args:
            film_id: Internal database film ID.
            keyword_id: Internal database keyword ID.
        """
        stmt = insert(FilmKeyword).values(
            film_id=film_id,
            keyword_id=keyword_id,
            source="tmdb",
        )
        stmt = stmt.on_conflict_do_nothing()
        self._session.execute(stmt)
