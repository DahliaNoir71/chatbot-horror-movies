"""Main Rotten Tomatoes enricher module."""

import asyncio
import json
import random
from typing import Any

from crawl4ai import AsyncWebCrawler

from src.etl.utils import setup_logger
from src.settings import settings

from .data_extractor import RTDataExtractor
from .search_scraper import RTSearchScraper


class RottenTomatoesEnricher:
    """Enriches film data with Rotten Tomatoes scores via web scraping."""

    def __init__(self) -> None:
        """Initialize the RT enricher with checkpoint management."""
        self.name = "RottenTomatoesEnricher"
        self.logger = setup_logger("etl.rt")
        self.checkpoint_path = settings.paths.checkpoints_dir / "rotten_tomatoes_processed.json"
        self.processed_films: set[str] = self._load_checkpoint()

        # Initialize sub-components
        self._searcher = RTSearchScraper(self.logger)
        self._extractor = RTDataExtractor(self.logger)

    # =========================================================================
    # CHECKPOINT MANAGEMENT
    # =========================================================================

    def _load_checkpoint(self) -> set[str]:
        """Load previously processed films from checkpoint file."""
        if not self.checkpoint_path.exists():
            return set()

        try:
            with self.checkpoint_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                processed = set(data.get("processed_films", []))
                self.logger.info(f"✅ Checkpoint loaded: {len(processed)} films")
                return processed
        except json.JSONDecodeError:
            self.logger.error("checkpoint_rt_corrupted")
            return set()

    def _save_checkpoint(self) -> None:
        """Persist processed films to checkpoint file."""
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with self.checkpoint_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {"processed_films": list(self.processed_films)},
                    f,
                    indent=2,
                )
        except OSError as e:
            self.logger.error(f"checkpoint_save_failed: {e}")

    # =========================================================================
    # FILM ENRICHMENT
    # =========================================================================

    async def enrich_film(self, crawler: AsyncWebCrawler, film: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a single film with RT data.

        Args:
            crawler: AsyncWebCrawler instance
            film: Film dict with title, year, etc.

        Returns:
            Enriched film dict or original if failed
        """
        title = film.get("title", "").strip()
        original_title = film.get("original_title", "").strip() or None
        # ✅ FIX: Support both "year" and "release_date" fields
        year = self._parse_year(film.get("year") or film.get("release_date"))
        film_id = f"{title}_{year}" if year else title

        # Skip if no title or already processed
        if not title or film_id in self.processed_films:
            return film

        try:
            film_url = await self._searcher.search_film(crawler, title, original_title, year)

            if film_url:
                details = await self._extractor.extract_film_details(crawler, film_url)
                if details:
                    self._finalize_enrichment(film_id, title, year, details)
                    return {**film, **details}

        except (TimeoutError, ConnectionError) as e:
            self.logger.error(f"Enrichment error for {title}: {e}")

        return film

    @staticmethod
    def _parse_year(year_value: str | int | float | None) -> int | None:
        """Parse year from various input formats."""
        if not year_value:
            return None
        try:
            return int(str(year_value).strip()[:4])
        except (ValueError, TypeError):
            return None

    def _finalize_enrichment(
        self,
        film_id: str,
        title: str,
        year: int | None,
        details: dict[str, Any],
    ) -> None:
        """Mark film as processed and log success."""
        self.processed_films.add(film_id)
        self._save_checkpoint()

        if "tomatometer_score" in details:
            tomatometer = details["tomatometer_score"]
            audience = details.get("audience_score", "N/A")
            self.logger.info(
                f"Enriched: {title} ({year or 'N/A'}) - "
                f"Tomatometer: {tomatometer}% | Audience: {audience}%"
            )

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    async def enrich_films_async(
        self, films: list[dict[str, Any]], max_concurrent: int = 3
    ) -> list[dict[str, Any]]:
        """
        Enrich multiple films with rate limiting.

        Args:
            films: List of film dicts to enrich
            max_concurrent: Max parallel requests

        Returns:
            List of enriched film dicts
        """
        if not films:
            return []

        self.logger.info(f"Starting enrichment of {len(films)} films")

        async with AsyncWebCrawler() as crawler:
            enriched_films = await self._process_batches(crawler, films, max_concurrent)

        enriched_count = sum(1 for f in enriched_films if f and "tomatometer_score" in f)
        self.logger.info(f"Enrichment complete: {enriched_count}/{len(films)} films")

        return enriched_films

    async def _process_batches(
        self,
        crawler: AsyncWebCrawler,
        films: list[dict[str, Any]],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        """Process films in batches with delays."""
        enriched: list[dict[str, Any]] = []

        for i in range(0, len(films), batch_size):
            batch = films[i : i + batch_size]
            batch_results = await self._process_single_batch(crawler, batch)
            enriched.extend(batch_results)

            # Delay between batches
            if i + batch_size < len(films):
                delay = random.uniform(2.0, 5.0)
                self.logger.info(f"Batch pause: {delay:.1f}s")
                await asyncio.sleep(delay)

        return enriched

    async def _process_single_batch(
        self, crawler: AsyncWebCrawler, batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process a single batch of films."""
        tasks = [self.enrich_film(crawler, film) for film in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed: list[dict[str, Any]] = []
        for film, result in zip(batch, results, strict=False):
            if isinstance(result, Exception):
                self.logger.error(f"Batch error: {result}")
                processed.append(film)
            elif result is not None:
                processed.append(result)
            else:
                processed.append(film)

        return processed


# =============================================================================
# PUBLIC UTILITY FUNCTION
# =============================================================================


async def enrich_films_with_rt(
    films: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Utility function to enrich films with Rotten Tomatoes data.

    Args:
        films: List of film dicts to enrich

    Returns:
        List of enriched film dicts
    """
    enricher = RottenTomatoesEnricher()
    return await enricher.enrich_films_async(films)
