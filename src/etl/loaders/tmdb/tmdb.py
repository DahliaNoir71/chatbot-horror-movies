"""TMDB loader orchestrator.

Coordinates loading of complete TMDB bundles from TMDBExtractor
into the database with proper ordering and transaction management.
"""

from typing import Any

from sqlalchemy.orm import Session

from src.etl.loaders.base import LoaderStats
from src.etl.loaders.tmdb.association import AssociationLoader
from src.etl.loaders.tmdb.credit import CreditLoader
from src.etl.loaders.tmdb.film import FilmLoader
from src.etl.loaders.tmdb.reference import ReferenceLoader
from src.etl.utils.logger import setup_logger


class TMDBLoader:
    """Orchestrates loading of TMDB extraction bundles.

    Handles the full pipelines from TMDBExtractor output
    to database insertion with proper FK ordering:
    1. Reference data (genres, keywords, companies, languages)
    2. Films
    3. Credits
    4. Associations (film_genres, film_keywords, etc.)
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._logger = setup_logger("etl.loader.tmdb")

        # Initialize sub-loaders
        self._ref = ReferenceLoader(session)
        self._film = FilmLoader(session)
        self._credit = CreditLoader(session)
        self._assoc = AssociationLoader(session, self._ref)

    @property
    def reference(self) -> ReferenceLoader:
        """Get reference data loader.

        Returns:
            ReferenceLoader instance.
        """
        return self._ref

    @property
    def film(self) -> FilmLoader:
        """Get film loader.

        Returns:
            FilmLoader instance.
        """
        return self._film

    @property
    def credit(self) -> CreditLoader:
        """Get credit loader.

        Returns:
            CreditLoader instance.
        """
        return self._credit

    @property
    def association(self) -> AssociationLoader:
        """Get association loader.

        Returns:
            AssociationLoader instance.
        """
        return self._assoc

    def load_bundle(self, bundle: dict[str, Any]) -> bool:
        """Load a single TMDB bundle into database.

        Args:
            bundle: Dict from TMDBExtractor with:
                - film: NormalizedFilmData
                - credits: list[NormalizedCreditData]
                - genres: list[NormalizedGenreData]
                - keywords: list[NormalizedKeywordData]
                - companies: list[NormalizedCompanyData]
                - languages: list[NormalizedLanguageData]
                - genre_ids: list[int] (TMDB genre IDs for associations)

        Returns:
            True if successful, False otherwise.
        """
        try:
            self._load_references(bundle)
            film_id = self._load_film(bundle)
            if film_id is None:
                return False

            self._load_credits(bundle, film_id)
            self._load_associations(bundle, film_id)
            return True

        except Exception as e:
            self._logger.error(f"Bundle load failed: {e}")
            return False

    def load_bundles(self, bundles: list[dict[str, Any]]) -> LoaderStats:
        """Load multiple bundles.

        Args:
            bundles: List of TMDB bundles.

        Returns:
            Combined LoaderStats.
        """
        stats = LoaderStats()
        total = len(bundles)

        self._logger.info(f"Loading {total} bundles")

        for idx, bundle in enumerate(bundles, 1):
            if self.load_bundle(bundle):
                stats.inserted += 1
            else:
                stats.errors += 1

            if idx % 50 == 0:
                self._logger.info(f"Progress: {idx}/{total}")
                self._session.flush()

        self._session.flush()
        self._logger.info(f"Complete: {stats.inserted} OK, {stats.errors} errors")
        return stats

    def _load_references(self, bundle: dict[str, Any]) -> None:
        """Load reference data from bundle.

        Args:
            bundle: TMDB bundle dictionary.
        """
        self._ref.load_all(
            genres=bundle.get("genres"),
            keywords=bundle.get("keywords"),
            companies=bundle.get("companies"),
            languages=bundle.get("languages"),
        )
        self._session.flush()

    def _load_film(self, bundle: dict[str, Any]) -> int | None:
        """Load film and return internal ID.

        Args:
            bundle: TMDB bundle dictionary.

        Returns:
            Internal film ID or None if load failed.
        """
        film_data = bundle.get("film")
        if not film_data:
            return None

        self._film.load([film_data])
        return self._film.get_id_by_tmdb_id(film_data["tmdb_id"])

    def _load_credits(self, bundle: dict[str, Any], film_id: int) -> None:
        """Load credits for film.

        Args:
            bundle: TMDB bundle dictionary.
            film_id: Internal database film ID.
        """
        if credits_data := bundle.get("credits"):
            self._credit.load({"credits": credits_data, "film_id": film_id})

    def _load_associations(self, bundle: dict[str, Any], film_id: int) -> None:
        """Load all associations for film.

        Args:
            bundle: TMDB bundle dictionary.
            film_id: Internal database film ID.
        """
        self._load_genre_associations(bundle, film_id)
        self._load_keyword_associations(bundle, film_id)
        self._load_company_associations(bundle, film_id)
        self._load_language_associations(bundle, film_id)

    def _load_genre_associations(self, bundle: dict[str, Any], film_id: int) -> None:
        """Load genre associations for film.

        Args:
            bundle: TMDB bundle dictionary.
            film_id: Internal database film ID.
        """
        if genre_ids := bundle.get("genre_ids"):
            self._assoc.load_genres(film_id, genre_ids)

    def _load_keyword_associations(self, bundle: dict[str, Any], film_id: int) -> None:
        """Load keyword associations for film.

        Args:
            bundle: TMDB bundle dictionary.
            film_id: Internal database film ID.
        """
        if keywords := bundle.get("keywords"):
            keyword_ids = [k["tmdb_keyword_id"] for k in keywords if k.get("tmdb_keyword_id")]
            if keyword_ids:
                self._assoc.load_keywords(film_id, keyword_ids)

    def _load_company_associations(self, bundle: dict[str, Any], film_id: int) -> None:
        """Load company associations for film.

        Args:
            bundle: TMDB bundle dictionary.
            film_id: Internal database film ID.
        """
        if companies := bundle.get("companies"):
            company_ids = [c["tmdb_company_id"] for c in companies if c.get("tmdb_company_id")]
            if company_ids:
                self._assoc.load_companies(film_id, company_ids)

    def _load_language_associations(self, bundle: dict[str, Any], film_id: int) -> None:
        """Load language associations for film.

        Args:
            bundle: TMDB bundle dictionary.
            film_id: Internal database film ID.
        """
        if languages := bundle.get("languages"):
            iso_codes = [lang["iso_639_1"] for lang in languages if lang.get("iso_639_1")]
            if iso_codes:
                self._assoc.load_languages(film_id, iso_codes)
