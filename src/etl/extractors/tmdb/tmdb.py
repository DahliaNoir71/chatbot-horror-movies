"""TMDB Extractor for horror films.

Orchestrates extraction of horror films from TMDB API
with discover, details enrichment, and checkpoint support.
"""

from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, TypedDict, Unpack

from src.etl.extractors.base import BaseExtractor
from src.etl.extractors.tmdb.client import TMDBClient, TMDBNotFoundError
from src.etl.extractors.tmdb.normalizer import TMDBNormalizer
from src.etl.types import (
    ETLResult,
    NormalizedCompanyData,
    NormalizedCreditData,
    NormalizedGenreData,
    NormalizedKeywordData,
    NormalizedLanguageData,
    TMDBFilmData,
)
from src.settings import settings


class TMDBExtractor(BaseExtractor):
    """Extracts horror films from TMDB API.

    Supports year-based batching, enrichment with details,
    and checkpoint-based resumption.

    Attributes:
        client: TMDB API client.
        normalizer: Data normalizer.
    """

    name = "tmdb"

    # Error messages
    _ERR_CLIENT_NOT_INITIALIZED = "Client not initialized"

    def __init__(self) -> None:
        """Initialize TMDB extractor."""
        super().__init__()
        self._client: TMDBClient | None = None
        self._normalizer = TMDBNormalizer()
        self._checkpoint_dir = Path("data/checkpoints")

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, **kwargs: Any) -> ETLResult:
        """Execute TMDB extraction.

        Args:
            **kwargs: Extraction parameters.
                year_min: Minimum year (default from settings).
                year_max: Maximum year (default from settings).
                enrich: Whether to fetch details (default from settings).
                resume: Whether to resume from checkpoint.

        Returns:
            ETLResult with extraction statistics.
        """
        year_min = kwargs.get("year_min", settings.tmdb.year_min)
        year_max = kwargs.get("year_max", settings.tmdb.year_max)
        enrich = kwargs.get("enrich", settings.tmdb.enrich_movies)
        resume = kwargs.get("resume", True)

        self._start_extraction()

        with TMDBClient() as client:
            self._client = client
            checkpoint = self._load_checkpoint() if resume else None
            start_year = self._get_start_year(checkpoint, year_min)

            for year in range(start_year, year_max + 1):
                self._extract_year(year, enrich, checkpoint)
                checkpoint = None

        return self._end_extraction()

    def _get_start_year(
        self,
        checkpoint: dict[str, Any] | None,
        default: int,
    ) -> int:
        """Get starting year from checkpoint or default.

        Args:
            checkpoint: Optional checkpoint data.
            default: Default starting year.

        Returns:
            Year to start extraction from.
        """
        if checkpoint:
            return checkpoint.get("last_year", default)
        return default

    def _extract_year(
        self,
        year: int,
        enrich: bool,
        checkpoint: dict[str, Any] | None,
    ) -> None:
        """Extract all horror films for a specific year.

        Args:
            year: Release year to extract.
            enrich: Whether to fetch details.
            checkpoint: Optional checkpoint data.
        """
        self.logger.info(f"Extracting year {year}")

        start_page = self._get_start_page(checkpoint, year)
        page = start_page
        total_pages = 1

        while page <= total_pages:
            result = self._extract_page(year, page, enrich)
            if result is None:
                break

            total_pages = min(result["total_pages"], settings.tmdb.max_pages)
            page += 1

            if settings.tmdb.save_checkpoints:
                self._save_year_checkpoint(year, page - 1)

        if settings.tmdb.save_checkpoints:
            self._clear_checkpoint()

    def _get_start_page(
        self,
        checkpoint: dict[str, Any] | None,
        year: int,
    ) -> int:
        """Get starting page from checkpoint.

        Args:
            checkpoint: Optional checkpoint data.
            year: Current extraction year.

        Returns:
            Page number to start from.
        """
        if checkpoint and checkpoint.get("last_year") == year:
            return checkpoint.get("last_page", 1) + 1
        return 1

    def _extract_page(
        self,
        year: int,
        page: int,
        enrich: bool,
    ) -> dict[str, Any] | None:
        """Extract a single page of discover results.

        Args:
            year: Release year.
            page: Page number.
            enrich: Whether to fetch details.

        Returns:
            Discover response or None on error.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        try:
            response = self._client.discover_movies(
                page=page,
                year=year,
                genre_id=settings.tmdb.horror_genre_id,
            )
        except Exception as e:
            self._log_error(f"Discover failed: year={year}, page={page}, error={e}")
            return None

        films = response.get("results", [])
        self.logger.debug(f"Page {page}: {len(films)} films")

        for film_data in films:
            self._process_film(film_data, enrich)

        return response

    def _process_film(self, film_data: TMDBFilmData, enrich: bool) -> None:
        """Process a single film from discover results.

        Args:
            film_data: Raw film data from discover.
            enrich: Whether to fetch additional details.
        """
        tmdb_id = film_data.get("id")
        if not tmdb_id:
            return

        try:
            if enrich:
                film_data = self._enrich_film(tmdb_id, film_data)

            self._extracted_count += 1
            self._log_periodic_progress()

        except Exception as e:
            self._log_error(f"Film {tmdb_id} processing failed: {e}")

    def _enrich_film(
        self,
        tmdb_id: int,
        base_data: TMDBFilmData,
    ) -> TMDBFilmData:
        """Enrich film with details, credits, keywords.

        Args:
            tmdb_id: TMDB movie ID.
            base_data: Base film data from discover.

        Returns:
            Enriched film data.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        try:
            details = self._client.get_movie_full(tmdb_id)
            return {**base_data, **details}
        except TMDBNotFoundError:
            self.logger.warning(f"Film {tmdb_id} not found for enrichment")
            return base_data

    def _log_periodic_progress(self) -> None:
        """Log progress at regular intervals."""
        interval = settings.tmdb.checkpoint_save_interval
        if self._extracted_count % interval == 0:
            self.logger.info(f"Extracted {self._extracted_count} films")

    # -------------------------------------------------------------------------
    # Type definitions for batch extraction parameters
    class _BatchExtractParams(TypedDict, total=False):
        """Parameters for batch extraction.

        All parameters are optional with the following defaults:
            year_min: settings.tmdb.year_min
            year_max: settings.tmdb.year_max
            enrich: settings.tmdb.enrich_movies
            batch_size: 20
        """

        year_min: int
        year_max: int
        enrich: bool
        batch_size: int

    # -------------------------------------------------------------------------
    # Batch Extraction with Callback
    # -------------------------------------------------------------------------

    def extract_with_callback(
        self,
        callback: Callable[[list[dict[str, Any]]], None],
        **kwargs: Unpack[_BatchExtractParams],
    ) -> ETLResult:
        """Extract films and call callback for each batch.

        Args:
            callback: Function to call with normalized data batches.
            **kwargs: Extraction parameters (year_min, year_max, enrich, batch_size).

        Returns:
            ETLResult with statistics.
        """
        params = self._parse_batch_params(kwargs)
        self._start_extraction()

        with TMDBClient() as client:
            self._client = client
            self._process_films_in_batches(params, callback)

        return self._end_extraction()

    def _parse_batch_params(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Parse extraction parameters from kwargs.

        Args:
            kwargs: Raw keyword arguments.

        Returns:
            Parsed parameters dict.
        """
        return {
            "year_min": kwargs.get("year_min", settings.tmdb.year_min),
            "year_max": kwargs.get("year_max", settings.tmdb.year_max),
            "enrich": kwargs.get("enrich", settings.tmdb.enrich_movies),
            "batch_size": kwargs.get("batch_size", 20),
        }

    def _process_films_in_batches(
        self,
        params: dict[str, Any],
        callback: Callable[[list[dict[str, Any]]], None],
    ) -> None:
        """Process all films and call callback for each batch.

        Args:
            params: Extraction parameters.
            callback: Batch callback function.
        """
        batch: list[dict[str, Any]] = []

        for film in self._iter_all_films(params):
            batch.append(film)
            self._extracted_count += 1

            if len(batch) >= params["batch_size"]:
                callback(batch)
                batch = []

        if batch:
            callback(batch)

    def _iter_all_films(
        self,
        params: dict[str, Any],
    ) -> Generator[dict[str, Any], None, None]:
        """Yield all processed films from all years.

        Args:
            params: Extraction parameters.

        Yields:
            Normalized film bundles.
        """
        for year in range(params["year_min"], params["year_max"] + 1):
            self.logger.info(f"Extracting year {year}")
            yield from self._iter_year_films(year, params["enrich"])

    def _iter_year_films(
        self,
        year: int,
        enrich: bool,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield all processed films for a specific year.

        Args:
            year: Release year.
            enrich: Whether to fetch details.

        Yields:
            Normalized film bundles.
        """
        page = 1
        total_pages = 1

        while page <= total_pages:
            response = self._fetch_page_safe(year, page)
            if response is None:
                break

            total_pages = min(response["total_pages"], settings.tmdb.max_pages)
            yield from self._iter_page_films(response, enrich)
            page += 1

    def _iter_page_films(
        self,
        response: dict[str, Any],
        enrich: bool,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield processed films from a page response.

        Args:
            response: TMDB discover response.
            enrich: Whether to fetch details.

        Yields:
            Normalized film bundles.
        """
        for film_data in response.get("results", []):
            processed = self._build_film_bundle(film_data, enrich)
            if processed:
                yield processed

    def _fetch_page_safe(self, year: int, page: int) -> dict | None:
        """Fetch discover page with error handling.

        Args:
            year: Release year.
            page: Page number.

        Returns:
            Response dict or None.
        """
        assert self._client is not None, self._ERR_CLIENT_NOT_INITIALIZED

        try:
            return self._client.discover_movies(
                page=page,
                year=year,
                genre_id=settings.tmdb.horror_genre_id,
            )
        except Exception as e:
            self._log_error(f"Fetch failed: year={year}, page={page}, error={e}")
            return None

    def _build_film_bundle(
        self,
        film_data: TMDBFilmData,
        enrich: bool,
    ) -> dict[str, Any] | None:
        """Build complete film data bundle.

        Args:
            film_data: Raw film from discover.
            enrich: Whether to fetch details.

        Returns:
            Dict with film, credits, genres, keywords, etc.
        """
        tmdb_id = film_data.get("id")
        if not tmdb_id:
            return None

        try:
            if enrich:
                film_data = self._enrich_film(tmdb_id, film_data)

            return self._normalize_bundle(film_data)

        except Exception as e:
            self._log_error(f"Bundle build failed for {tmdb_id}: {e}")
            return None

    def _normalize_bundle(self, film_data: TMDBFilmData) -> dict[str, Any]:
        """Normalize all film data into a bundle.

        Args:
            film_data: Enriched film data.

        Returns:
            Dict with normalized film and relations.
        """
        return {
            "film": self._normalizer.normalize_film(film_data, "tmdb_api"),
            "credits": self._extract_credits(film_data),
            "genres": self._extract_genres(film_data),
            "keywords": self._extract_keywords(film_data),
            "companies": self._extract_companies(film_data),
            "languages": self._extract_languages(film_data),
            "genre_ids": film_data.get("genre_ids", []),
        }

    def _extract_credits(self, film_data: TMDBFilmData) -> list[NormalizedCreditData]:
        """Extract and normalize credits from film data.

        Args:
            film_data: Enriched film data.

        Returns:
            List of normalized credits.
        """
        if "credits" not in film_data:
            return []

        return self._normalizer.normalize_credits(
            film_data["credits"].get("cast", []),
            film_data["credits"].get("crew", []),
        )

    def _extract_genres(self, film_data: TMDBFilmData) -> list[NormalizedGenreData]:
        """Extract and normalize genres from film data.

        Args:
            film_data: Enriched film data.

        Returns:
            List of normalized genres.
        """
        if "genres" not in film_data:
            return []

        return self._normalizer.normalize_genres(film_data["genres"])

    def _extract_keywords(
        self,
        film_data: TMDBFilmData,
    ) -> list[NormalizedKeywordData]:
        """Extract and normalize keywords from film data.

        Args:
            film_data: Enriched film data.

        Returns:
            List of normalized keywords.
        """
        if "keywords" not in film_data:
            return []

        kw_data = film_data["keywords"]
        kw_list = kw_data if isinstance(kw_data, list) else kw_data.get("keywords", [])
        return self._normalizer.normalize_keywords(kw_list)

    def _extract_companies(
        self,
        film_data: TMDBFilmData,
    ) -> list[NormalizedCompanyData]:
        """Extract and normalize production companies from film data.

        Args:
            film_data: Enriched film data.

        Returns:
            List of normalized companies.
        """
        if "production_companies" not in film_data:
            return []

        return self._normalizer.normalize_companies(film_data["production_companies"])

    def _extract_languages(
        self,
        film_data: TMDBFilmData,
    ) -> list[NormalizedLanguageData]:
        """Extract and normalize spoken languages from film data.

        Args:
            film_data: Enriched film data.

        Returns:
            List of normalized languages.
        """
        if "spoken_languages" not in film_data:
            return []

        return self._normalizer.normalize_languages(film_data["spoken_languages"])

    # -------------------------------------------------------------------------
    # Single Film Extraction
    # -------------------------------------------------------------------------

    def extract_film(self, tmdb_id: int) -> dict[str, Any] | None:
        """Extract a single film by TMDB ID.

        Args:
            tmdb_id: TMDB movie ID.

        Returns:
            Normalized film bundle or None.
        """
        with TMDBClient() as client:
            self._client = client

            try:
                film_data = self._client.get_movie_full(tmdb_id)
                return self._normalize_bundle(film_data)
            except TMDBNotFoundError:
                self.logger.warning(f"Film {tmdb_id} not found")
                return None
            except Exception as e:
                self.logger.error(f"Failed to extract film {tmdb_id}: {e}")
                return None

    # -------------------------------------------------------------------------
    # Checkpoint Management
    # -------------------------------------------------------------------------

    def _get_checkpoint_path(self) -> Path:
        """Get checkpoint file path.

        Returns:
            Path to checkpoint file.
        """
        return self._checkpoint_dir / "tmdb_checkpoint.json"

    def _load_checkpoint(self) -> dict[str, Any] | None:
        """Load extraction checkpoint.

        Returns:
            Checkpoint data or None.
        """
        return self.load_checkpoint(self._get_checkpoint_path())

    def _save_year_checkpoint(self, year: int, page: int) -> None:
        """Save checkpoint for current progress.

        Args:
            year: Current year.
            page: Current page.
        """
        checkpoint = self.create_checkpoint(last_year=year, last_page=page)
        self.save_checkpoint(checkpoint, self._get_checkpoint_path())

    def _clear_checkpoint(self) -> None:
        """Clear checkpoint file."""
        self.delete_checkpoint(self._get_checkpoint_path())

    # -------------------------------------------------------------------------
    # Genre Sync
    # -------------------------------------------------------------------------

    def extract_genres(self) -> list[NormalizedGenreData]:
        """Extract all TMDB genres.

        Returns:
            List of normalized genres.
        """
        with TMDBClient() as client:
            self._client = client

            try:
                response = self._client.get_genres()
                raw_genres = response.get("genres", [])
                return self._normalizer.normalize_genres(raw_genres)
            except Exception as e:
                self.logger.error(f"Failed to extract genres: {e}")
                return []
