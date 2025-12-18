"""Data extraction from RT film pages."""

import asyncio
import json
import logging
import random
from typing import Any

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from tenacity import retry, stop_after_attempt, wait_exponential


class RTDataExtractor:
    """Extracts film data from RT movie pages."""

    def __init__(self, logger: logging.Logger) -> None:
        """
        Initialize data extractor.

        Args:
            logger: Logger instance for output
        """
        self.logger = logger
        self.base_url = "https://www.rottentomatoes.com"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def extract_film_details(self, crawler: AsyncWebCrawler, film_url: str) -> dict[str, Any]:
        """
        Extract all available data from film page.

        Args:
            crawler: AsyncWebCrawler instance
            film_url: Relative URL of film

        Returns:
            Dict with extracted film details
        """
        full_url = f"{self.base_url}{film_url}"
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

        success, soup, json_data = await self._fetch_film_page(crawler, full_url, run_config)

        if not success:
            return {}

        details: dict[str, Any] = {"rotten_tomatoes_url": full_url}

        # Extract from JSON scorecard
        if json_data:
            self._extract_scores(json_data, details)

        # Extract from HTML
        if soup:
            self._extract_html_metadata(soup, details)

        self.logger.info(f"✓ Extracted details for {film_url}")
        return details

    async def _fetch_film_page(
        self,
        crawler: AsyncWebCrawler,
        full_url: str,
        run_config: CrawlerRunConfig,
    ) -> tuple[bool, BeautifulSoup | None, dict[str, Any] | None]:
        """
        Fetch and parse film page content.

        Args:
            crawler: AsyncWebCrawler instance
            full_url: Complete URL to fetch
            run_config: Crawler configuration

        Returns:
            Tuple of (success, soup, json_data)
        """
        try:
            await asyncio.sleep(random.uniform(1.5, 3.5))
            result = await crawler.arun(url=full_url, config=run_config)

            if not result.success or not result.html:
                return False, None, None

            soup = BeautifulSoup(result.html, "html.parser")
            json_data = self._extract_scorecard_json(soup)

            return True, soup, json_data

        except (TimeoutError, ConnectionError) as e:
            self.logger.error(f"❌ Fetch error for {full_url}: {e}")
            return False, None, None

    @staticmethod
    def _extract_scorecard_json(soup: BeautifulSoup) -> dict[str, Any] | None:
        """Extract JSON data from embedded script tag."""
        script_tag = soup.select_one("script#media-scorecard-json")
        if not script_tag or not script_tag.string:
            return None

        try:
            return json.loads(script_tag.string.strip())
        except json.JSONDecodeError:
            return None

    # =========================================================================
    # SCORE EXTRACTION
    # =========================================================================

    def _extract_scores(self, scorecard: dict[str, Any], details: dict[str, Any]) -> None:
        """
        Extract critic and audience scores from scorecard JSON.

        Args:
            scorecard: Parsed JSON scorecard data
            details: Dict to populate with scores
        """
        self._extract_critics_scores(scorecard, details)
        self._extract_audience_scores(scorecard, details)

    @staticmethod
    def _extract_critics_scores(scorecard: dict[str, Any], details: dict[str, Any]) -> None:
        """Extract Tomatometer and critic metrics."""
        critics = scorecard.get("criticsScore")
        if not critics:
            return

        if score := critics.get("score"):
            details["tomatometer_score"] = int(score)
        if certified := critics.get("certified"):
            details["certified_fresh"] = certified

        details["critics_count"] = critics.get("reviewCount", 0)
        details["critics_average_rating"] = critics.get("averageRating")

    @staticmethod
    def _extract_audience_scores(scorecard: dict[str, Any], details: dict[str, Any]) -> None:
        """Extract audience score and metrics."""
        audience = scorecard.get("audienceScore")
        if not audience:
            return

        if score := audience.get("score"):
            details["audience_score"] = int(score)

        details["audience_count"] = audience.get("reviewCount", 0)
        details["audience_average_rating"] = audience.get("averageRating")

    # =========================================================================
    # HTML METADATA EXTRACTION
    # =========================================================================

    def _extract_html_metadata(self, soup: BeautifulSoup, details: dict[str, Any]) -> None:
        """
        Extract additional metadata from HTML.

        Args:
            soup: Parsed HTML
            details: Dict to populate
        """
        self._extract_consensus(soup, details)
        self._extract_genres(soup, details)
        self._extract_movie_info(soup, details)

    @staticmethod
    def _extract_consensus(soup: BeautifulSoup, details: dict[str, Any]) -> None:
        """Extract critics consensus text."""
        # Try multiple selectors (RT changes structure frequently)
        selectors = [
            "#critics-consensus p",
            "[data-qa='critics-consensus'] p",
            ".critics-consensus p",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = " ".join(elem.stripped_strings)
                if text and text != "No consensus yet.":
                    details["critics_consensus"] = text
                    return

    @staticmethod
    def _extract_genres(soup: BeautifulSoup, details: dict[str, Any]) -> None:
        """Extract film genres from page."""
        # Look for genre links in info section
        genre_links = soup.select("a[href*='/browse/movies_in_theaters/genres/']")
        if not genre_links:
            genre_links = soup.select("a[href*='/browse/movies/genre/']")

        if genre_links:
            genres = [link.get_text(strip=True) for link in genre_links]
            details["rt_genres"] = [g for g in genres if g]

    @staticmethod
    def _extract_movie_info(soup: BeautifulSoup, details: dict[str, Any]) -> None:
        """Extract rating, runtime from movie info section."""
        # Try to find info items
        for item in soup.select("li.info-item"):
            label = item.select_one(".info-item-label")
            value = item.select_one(".info-item-value")

            if not label or not value:
                continue

            label_text = label.get_text(strip=True)
            value_text = value.get_text(strip=True)

            if "Rating" in label_text and value_text:
                details["rt_rating"] = value_text
            elif "Runtime" in label_text and value_text:
                details["rt_runtime"] = value_text
