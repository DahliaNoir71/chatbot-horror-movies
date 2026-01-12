"""Rotten Tomatoes web scraper using Crawl4AI.

Handles searching for films and extracting data from
film pages using BeautifulSoup for HTML parsing.
"""

import asyncio
import json
import logging
import random
from typing import Any

from bs4 import BeautifulSoup, Tag
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    CrawlResult,
)

from src.etl.extractors.rotten_tomatoes.url_builder import RTUrlBuilder

# Year tolerance for matching RT vs source year
YEAR_TOLERANCE = 1


class RTScraper:
    """Scrapes Rotten Tomatoes for film data.

    Uses Crawl4AI for browser-based scraping with
    BeautifulSoup for HTML parsing.

    Attributes:
        logger: Logger instance.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize scraper.

        Args:
            logger: Optional logger instance.
        """
        self._logger = logger or logging.getLogger(__name__)
        self._browser_config = self._create_browser_config()

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    @staticmethod
    def _create_browser_config() -> BrowserConfig:
        """Create browser configuration for Crawl4AI.

        Returns:
            BrowserConfig instance for Chromium headless.
        """
        return BrowserConfig(
            browser_type="chromium",
            headless=True,
            verbose=False,
        )

    @staticmethod
    def _create_run_config(timeout: int = 30000) -> CrawlerRunConfig:
        """Create run configuration for a crawl.

        Args:
            timeout: Page timeout in milliseconds.

        Returns:
            CrawlerRunConfig instance.
        """
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=timeout,
            delay_before_return_html=1.0,
        )

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search_film(
        self,
        crawler: AsyncWebCrawler,
        title: str,
        original_title: str | None = None,
        year: int | None = None,
    ) -> str | None:
        """Search for film using multiple strategies.

        Strategy order:
        1. RT search page scraping (most reliable)
        2. Direct URL variants (fallback)

        Args:
            crawler: AsyncWebCrawler instance.
            title: Primary film title.
            original_title: Alternative title.
            year: Release year for validation.

        Returns:
            Relative URL if found, None otherwise.
        """
        # Strategy 1: Search page with primary title
        url = await self._search_via_page(crawler, title, year)
        if url:
            return url

        # Strategy 2: Search with original title if different
        if original_title and original_title.lower() != title.lower():
            url = await self._search_via_page(crawler, original_title, year)
            if url:
                return url

        # Strategy 3: Direct URL variants
        return await self._try_url_variants(crawler, title, original_title, year)

    async def _search_via_page(
        self,
        crawler: AsyncWebCrawler,
        title: str,
        year: int | None,
    ) -> str | None:
        """Search film via RT search page.

        Args:
            crawler: AsyncWebCrawler instance.
            title: Film title to search.
            year: Optional year for validation.

        Returns:
            Relative film URL or None.
        """
        search_url = RTUrlBuilder.build_search_url(title, year)
        run_config = self._create_run_config(timeout=20000)

        try:
            await self._random_delay(0.5, 1.5)
            result = await crawler.arun(url=search_url, config=run_config)

            if not result.success or not result.html:
                self._logger.debug(f"Search failed for: {title}")
                return None

            return self._parse_search_results(result.html, title, year)

        except (TimeoutError, ConnectionError) as e:
            self._logger.warning(f"Search error for {title}: {e}")
            return None

    def _parse_search_results(
        self,
        html: str,
        title: str,
        year: int | None,
    ) -> str | None:
        """Parse search results HTML to find matching film.

        Args:
            html: Search page HTML.
            title: Original title for matching.
            year: Year for validation.

        Returns:
            Relative URL of best match or None.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Find movie search results
        items = soup.select("search-page-media-row[data-qa='data-row']")
        if not items:
            # Fallback: try older selector
            items = soup.select("[data-qa='search-result']")

        for item in items:
            candidate = self._extract_search_item(item)
            if candidate and self._is_match(candidate, title, year):
                self._logger.info(f"✅ Found match: {candidate['url']}")
                return candidate["url"]

        return None

    @staticmethod
    def _extract_search_item(item: Tag) -> dict[str, Any] | None:
        """Extract data from search result element.

        Args:
            item: BeautifulSoup Tag element.

        Returns:
            Dict with url, title, year or None.
        """
        try:
            return RTScraper._parse_search_item_data(item)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _parse_search_item_data(item: Tag) -> dict[str, Any] | None:
        """Parse data from search item tag.

        Args:
            item: BeautifulSoup Tag element.

        Returns:
            Dict with url, title, year or None.
        """
        # Try multiple link selectors
        link = item.select_one("a[data-qa='info-name']")
        if not link:
            link = item.select_one("a[href^='/m/']")

        if not link:
            return None

        href = link.get("href", "")
        if not href.startswith("/m/"):
            return None

        # Extract year from attribute or text
        year_str = item.get("releaseyear", "")
        year = int(year_str) if year_str and str(year_str).isdigit() else None

        title_text = link.get_text(strip=True)

        return {"url": href, "title": title_text, "year": year}

    @staticmethod
    def _is_match(
        candidate: dict[str, Any],
        title: str,
        year: int | None,
    ) -> bool:
        """Check if candidate matches search criteria.

        Args:
            candidate: Candidate result dict.
            title: Original title.
            year: Expected year.

        Returns:
            True if candidate matches.
        """
        # Must have valid URL
        if not candidate.get("url"):
            return False

        # Year validation if provided
        if year and candidate.get("year"):
            year_diff = abs(candidate["year"] - year)
            if year_diff > YEAR_TOLERANCE:
                return False

        return True

    # -------------------------------------------------------------------------
    # URL Variants Fallback
    # -------------------------------------------------------------------------

    async def _try_url_variants(
        self,
        crawler: AsyncWebCrawler,
        title: str,
        original_title: str | None,
        year: int | None,
    ) -> str | None:
        """Try direct URL variants as fallback.

        Args:
            crawler: AsyncWebCrawler instance.
            title: Primary title.
            original_title: Alternative title.
            year: Release year.

        Returns:
            Valid URL if found, None otherwise.
        """
        variants = RTUrlBuilder.generate_url_variants(title, year)

        if original_title and original_title.lower() != title.lower():
            variants.extend(RTUrlBuilder.generate_url_variants(original_title, year))

        for film_url in variants:
            if await self._check_url_valid(crawler, film_url):
                self._logger.info(f"✅ URL variant valid: {film_url}")
                return film_url

        return None

    async def _check_url_valid(
        self,
        crawler: AsyncWebCrawler,
        film_url: str,
    ) -> bool:
        """Check if film URL returns valid page.

        Args:
            crawler: AsyncWebCrawler instance.
            film_url: Relative URL to check.

        Returns:
            True if page exists and is valid.
        """
        full_url = RTUrlBuilder.build_full_url(film_url)
        run_config = self._create_run_config(timeout=15000)

        try:
            await self._random_delay(0.5, 1.0)
            result = await crawler.arun(url=full_url, config=run_config)

            return self._is_valid_film_page(result)

        except (TimeoutError, ConnectionError):
            return False

    @staticmethod
    def _is_valid_film_page(result: CrawlResult) -> bool:
        """Validate crawl result is a valid film page.

        Args:
            result: CrawlResult object from Crawl4AI.

        Returns:
            True if valid film page.
        """
        if not result.success or not result.html:
            return False

        is_not_404 = "404 - Not Found" not in result.html
        has_scorecard = "media-scorecard-json" in result.html

        return is_not_404 and has_scorecard

    # -------------------------------------------------------------------------
    # Data Extraction
    # -------------------------------------------------------------------------

    async def extract_film_data(
        self,
        crawler: AsyncWebCrawler,
        film_url: str,
    ) -> dict[str, Any]:
        """Extract film data from RT page.

        Args:
            crawler: AsyncWebCrawler instance.
            film_url: Relative or full URL.

        Returns:
            Dict with extracted film details.
        """
        full_url = RTUrlBuilder.build_full_url(film_url)
        run_config = self._create_run_config()

        try:
            await self._random_delay(1.0, 2.5)
            result = await crawler.arun(url=full_url, config=run_config)

            if not result.success or not result.html:
                self._logger.warning(f"Failed to fetch: {full_url}")
                return {}

            return self._parse_film_page(result.html, full_url)

        except Exception as e:
            self._logger.error(f"Extract error for {film_url}: {e}")
            return {}

    def _parse_film_page(self, html: str, url: str) -> dict[str, Any]:
        """Parse film page HTML.

        Args:
            html: Page HTML content.
            url: Page URL.

        Returns:
            Dict with extracted data.
        """
        soup = BeautifulSoup(html, "html.parser")
        details: dict[str, Any] = {"rt_url": url}

        # Extract from JSON scorecard
        scorecard = self._extract_scorecard_json(soup)
        if scorecard:
            self._extract_scores(scorecard, details)

        # Extract from HTML
        self._extract_html_metadata(soup, details)

        return details

    # -------------------------------------------------------------------------
    # JSON Scorecard Extraction
    # -------------------------------------------------------------------------

    def _extract_scorecard_json(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        """Extract JSON data from embedded script tag.

        Args:
            soup: Parsed HTML.

        Returns:
            Parsed JSON dict or None.
        """
        script_tag = soup.select_one("script#media-scorecard-json")
        if not script_tag or not script_tag.string:
            return None

        try:
            return json.loads(script_tag.string.strip())
        except json.JSONDecodeError:
            self._logger.debug("Failed to parse scorecard JSON")
            return None

    @staticmethod
    def _extract_scores(
        scorecard: dict[str, Any],
        details: dict[str, Any],
    ) -> None:
        """Extract scores from scorecard JSON.

        Args:
            scorecard: Parsed JSON scorecard.
            details: Dict to populate.
        """
        RTScraper._extract_critics_scores(scorecard, details)
        RTScraper._extract_audience_scores(scorecard, details)
        RTScraper._extract_consensus_from_json(scorecard, details)

    @staticmethod
    def _extract_critics_scores(
        scorecard: dict[str, Any],
        details: dict[str, Any],
    ) -> None:
        """Extract Tomatometer and critic metrics.

        Args:
            scorecard: JSON scorecard data.
            details: Dict to populate.
        """
        critics = scorecard.get("criticsScore")
        if not critics:
            return

        if score := critics.get("score"):
            details["tomatometer_score"] = int(score)

        if certified := critics.get("certified"):
            details["certified_fresh"] = certified

        details["critics_count"] = critics.get("reviewCount", 0)
        details["critics_average_rating"] = critics.get("averageRating")

        if sentiment := critics.get("sentiment"):
            details["tomatometer_state"] = sentiment.lower()

    @staticmethod
    def _extract_audience_scores(
        scorecard: dict[str, Any],
        details: dict[str, Any],
    ) -> None:
        """Extract audience score and metrics.

        Args:
            scorecard: JSON scorecard data.
            details: Dict to populate.
        """
        audience = scorecard.get("audienceScore")
        if not audience:
            return

        if score := audience.get("score"):
            details["audience_score"] = int(score)

        details["audience_count"] = audience.get("reviewCount", 0)
        details["audience_average_rating"] = audience.get("averageRating")

        if sentiment := audience.get("sentiment"):
            details["audience_state"] = sentiment.lower()

    @staticmethod
    def _extract_consensus_from_json(
        scorecard: dict[str, Any],
        details: dict[str, Any],
    ) -> None:
        """Extract critics consensus from JSON.

        Args:
            scorecard: JSON scorecard data.
            details: Dict to populate.
        """
        if consensus := scorecard.get("description"):
            details["critics_consensus"] = consensus

    # -------------------------------------------------------------------------
    # HTML Metadata Extraction
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract_html_metadata(
        soup: BeautifulSoup,
        details: dict[str, Any],
    ) -> None:
        """Extract additional metadata from HTML.

        Args:
            soup: Parsed HTML.
            details: Dict to populate.
        """
        RTScraper._extract_consensus_from_html(soup, details)
        RTScraper._extract_rating(soup, details)

    @staticmethod
    def _extract_consensus_from_html(
        soup: BeautifulSoup,
        details: dict[str, Any],
    ) -> None:
        """Extract critics consensus from HTML if not in JSON.

        Args:
            soup: Parsed HTML.
            details: Dict to populate.
        """
        if details.get("critics_consensus"):
            return

        # Try multiple selectors
        selectors = [
            "[data-qa='critics-consensus']",
            ".critics-consensus",
            ".what-to-know__section-body",
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text and len(text) > 20:
                    details["critics_consensus"] = text
                    break

    @staticmethod
    def _extract_rating(
        soup: BeautifulSoup,
        details: dict[str, Any],
    ) -> None:
        """Extract MPAA rating from HTML.

        Args:
            soup: Parsed HTML.
            details: Dict to populate.
        """
        rating_elem = soup.select_one("[data-qa='info-rating']")
        if rating_elem:
            details["rt_rating"] = rating_elem.get_text(strip=True)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    async def _random_delay(min_sec: float, max_sec: float) -> None:
        """Add random delay between requests.

        Args:
            min_sec: Minimum delay seconds.
            max_sec: Maximum delay seconds.
        """
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
