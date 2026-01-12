"""Rotten Tomatoes extractor for film enrichment.

Orchestrates scraping of RT data to enrich films
already in the database with critics scores.
"""

import asyncio
from pathlib import Path
from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig

from src.etl.extractors.base import BaseExtractor
from src.etl.extractors.rotten_tomatoes.normalizer import RTNormalizer
from src.etl.extractors.rotten_tomatoes.scraper import RTScraper
from src.etl.types import ETLResult, NormalizedRTScoreData


class RTExtractor(BaseExtractor):
    """Extracts Rotten Tomatoes data for film enrichment.

    This extractor is designed to enrich existing films
    with RT scores, not as a primary data source.

    Attributes:
        scraper: RT web scraper.
        normalizer: Data normalizer.
    """

    name = "rotten_tomatoes"

    def __init__(self) -> None:
        """Initialize RT extractor."""
        super().__init__()
        self._scraper = RTScraper(self.logger)
        self._normalizer = RTNormalizer(self.logger)
        self._checkpoint_dir = Path("data/checkpoints")
        self._browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            verbose=False,
        )

    # -------------------------------------------------------------------------
    # Main Extraction
    # -------------------------------------------------------------------------

    def extract(self, **kwargs: Any) -> ETLResult:
        """Execute RT extraction (sync wrapper).

        Kwargs:
            films: List of film dicts with title, year, id.
            resume: Whether to resume from checkpoint.

        Returns:
            ETLResult with extraction statistics.
        """
        films = kwargs.get("films", [])
        resume = kwargs.get("resume", True)

        return asyncio.run(self.extract_async(films=films, resume=resume))

    async def extract_async(
        self,
        films: list[dict[str, Any]],
        resume: bool = True,
    ) -> ETLResult:
        """Execute RT extraction asynchronously.

        Args:
            films: List of films to enrich.
            resume: Whether to resume from checkpoint.

        Returns:
            ETLResult with statistics.
        """
        self._start_extraction()
        self.logger.info(f"Starting enrichment of {len(films)} films")

        # Load checkpoint if resuming
        processed_ids = self._load_processed_ids() if resume else set()
        remaining = [f for f in films if f.get("id") not in processed_ids]

        self.logger.info(f"Remaining to process: {len(remaining)}")

        async with AsyncWebCrawler(config=self._browser_config) as crawler:
            for idx, film in enumerate(remaining):
                await self._process_film(crawler, film)

                # Save checkpoint periodically
                if (idx + 1) % 10 == 0:
                    self._save_processed_ids(processed_ids | {film["id"]})

                # Log progress
                if (idx + 1) % 25 == 0:
                    self._log_progress(idx + 1, len(remaining))

            # Clear checkpoint on completion
            self._clear_checkpoint()

        return self._end_extraction()

    async def _process_film(
        self,
        crawler: AsyncWebCrawler,
        film: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Process a single film.

        Args:
            crawler: AsyncWebCrawler instance.
            film: Film dict with title, year, id.

        Returns:
            Extracted data or None.
        """
        title = film.get("title", "")
        original_title = film.get("original_title")
        year = film.get("year")

        try:
            # Search for film on RT
            film_url = await self._scraper.search_film(crawler, title, original_title, year)

            if not film_url:
                self.logger.debug(f"Not found: {title} ({year})")
                return None

            # Extract data
            raw_data = await self._scraper.extract_film_data(crawler, film_url)

            if raw_data:
                self._extracted_count += 1
                self.logger.info(f"✓ Enriched: {title}")

            return raw_data

        except Exception as e:
            self._log_error(f"Error processing {title}: {e}")
            return None

    # -------------------------------------------------------------------------
    # Batch Extraction with Callback
    # -------------------------------------------------------------------------

    async def extract_with_callback(
        self,
        films: list[dict[str, Any]],
        callback: callable,
        batch_size: int = 10,
    ) -> ETLResult:
        """Extract films and call callback for each batch.

        Args:
            films: List of films to enrich.
            callback: Function to call with normalized results.
            batch_size: Number of films per batch.

        Returns:
            ETLResult with statistics.
        """
        self._start_extraction()
        self.logger.info(f"Starting batch enrichment of {len(films)} films")

        batch: list[tuple[int, dict[str, Any]]] = []

        async with AsyncWebCrawler(config=self._browser_config) as crawler:
            for film in films:
                film_id = film.get("id")
                raw_data = await self._process_film(crawler, film)

                if raw_data and film_id:
                    batch.append((film_id, raw_data))

                if len(batch) >= batch_size:
                    normalized = self._normalizer.normalize_batch(batch)
                    if normalized:
                        callback(normalized)
                    batch = []

            # Final batch
            if batch:
                normalized = self._normalizer.normalize_batch(batch)
                if normalized:
                    callback(normalized)

        return self._end_extraction()

    # -------------------------------------------------------------------------
    # Single Film Extraction
    # -------------------------------------------------------------------------

    async def extract_film(
        self,
        title: str,
        year: int | None = None,
        original_title: str | None = None,
    ) -> dict[str, Any] | None:
        """Extract RT data for a single film.

        Args:
            title: Film title.
            year: Release year.
            original_title: Alternative title.

        Returns:
            Raw extracted data or None.
        """
        async with AsyncWebCrawler(config=self._browser_config) as crawler:
            film_url = await self._scraper.search_film(crawler, title, original_title, year)

            if not film_url:
                self.logger.warning(f"Film not found: {title}")
                return None

            return await self._scraper.extract_film_data(crawler, film_url)

    def extract_and_normalize(
        self,
        title: str,
        film_id: int,
        year: int | None = None,
        original_title: str | None = None,
    ) -> NormalizedRTScoreData | None:
        """Extract and normalize RT data for a film.

        Args:
            title: Film title.
            film_id: Database film ID.
            year: Release year.
            original_title: Alternative title.

        Returns:
            Normalized data or None.
        """
        raw_data = asyncio.run(self.extract_film(title, year, original_title))

        if not raw_data:
            return None

        return self._normalizer.normalize(raw_data, film_id)

    # -------------------------------------------------------------------------
    # Checkpoint Management
    # -------------------------------------------------------------------------

    def _get_checkpoint_path(self) -> Path:
        """Get checkpoint file path."""
        return self._checkpoint_dir / "rt_checkpoint.json"

    def _load_processed_ids(self) -> set[int]:
        """Load set of processed film IDs."""
        checkpoint = self.load_checkpoint(self._get_checkpoint_path())
        if checkpoint and "processed_ids" in checkpoint:
            return set(checkpoint["processed_ids"])
        return set()

    def _save_processed_ids(self, processed_ids: set[int]) -> None:
        """Save processed film IDs to checkpoint.

        Args:
            processed_ids: Set of processed IDs.
        """
        checkpoint = self.create_checkpoint(processed_ids=list(processed_ids))
        self.save_checkpoint(checkpoint, self._get_checkpoint_path())

    def _clear_checkpoint(self) -> None:
        """Clear checkpoint file."""
        self.delete_checkpoint(self._get_checkpoint_path())

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def get_films_to_enrich(
        self,
        films: list[dict[str, Any]],
        existing_ids: set[int],
    ) -> list[dict[str, Any]]:
        """Filter films that need RT enrichment.

        Args:
            films: All films.
            existing_ids: Films that already have RT data.

        Returns:
            Films without RT data.
        """
        return [f for f in films if f.get("id") not in existing_ids]
