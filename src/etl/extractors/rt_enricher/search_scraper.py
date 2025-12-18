"""RT search page scraping for film URL discovery."""

import asyncio
import logging
import random
from typing import Any

from bs4 import BeautifulSoup, Tag
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig, CrawlResult

from .url_builder import RTUrlBuilder

# Year tolerance for matching (RT vs TMDB)
YEAR_TOLERANCE = 1


class RTSearchScraper:
    """Scrapes RT search page to find film URLs."""

    def __init__(self, logger: logging.Logger) -> None:
        """
        Initialize search scraper.

        Args:
            logger: Logger instance for output
        """
        self.logger = logger
        self.base_url = "https://www.rottentomatoes.com"

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
            crawler: AsyncWebCrawler instance
            title: Primary film title
            original_title: Alternative title
            year: Release year for validation

        Returns:
            Relative URL if found, None otherwise
        """
        url = await self._search_with_all_strategies(crawler, title, original_title, year)

        if not url:
            self.logger.warning(f"❌ Film not found: {title} ({year or 'N/A'})")

        return url

    async def _search_with_all_strategies(
        self,
        crawler: AsyncWebCrawler,
        title: str,
        original_title: str | None,
        year: int | None,
    ) -> str | None:
        """Execute all search strategies in order.

        Args:
            crawler: AsyncWebCrawler instance
            title: Primary film title
            original_title: Alternative title
            year: Release year for validation

        Returns:
            Relative URL if found, None otherwise
        """
        # Strategy 1: RT search page with primary title
        url = await self._search_via_rt_page(crawler, title, year)
        if url:
            return url

        # Strategy 2: RT search with original title if different
        if original_title and original_title.lower() != title.lower():
            url = await self._search_via_rt_page(crawler, original_title, year)
            if url:
                return url

        # Strategy 3: Direct URL variants (last resort)
        return await self._try_url_variants(crawler, title, original_title, year)

    # =========================================================================
    # RT SEARCH PAGE SCRAPING
    # =========================================================================

    async def _search_via_rt_page(
        self,
        crawler: AsyncWebCrawler,
        title: str,
        year: int | None = None,
    ) -> str | None:
        """
        Search film via RT search page and extract real URL.

        Args:
            crawler: AsyncWebCrawler instance
            title: Film title to search
            year: Release year for validation

        Returns:
            Relative URL if found, None otherwise
        """
        search_url = RTUrlBuilder.build_search_url(title)
        results = await self._fetch_search_results(crawler, search_url)

        if not results:
            self.logger.debug(f"No RT search results for: {title}")
            return None

        return self._find_best_match(results, year)

    async def _fetch_search_results(
        self, crawler: AsyncWebCrawler, search_url: str
    ) -> list[dict[str, Any]]:
        """
        Fetch and parse RT search page results.

        Args:
            crawler: AsyncWebCrawler instance
            search_url: Full search URL

        Returns:
            List of search result dicts
        """
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=30000,
        )

        try:
            await asyncio.sleep(random.uniform(1.0, 2.5))
            result = await crawler.arun(url=search_url, config=run_config)

            if not result.success or not result.html:
                return []

            return self._parse_search_results(result.html)

        except (TimeoutError, ConnectionError) as e:
            self.logger.error(f"❌ RT search failed: {e}")
            return []

    def _parse_search_results(self, html: str) -> list[dict[str, Any]]:
        """
        Parse movie results from RT search page HTML.

        Args:
            html: Raw HTML content

        Returns:
            List of parsed results with url, title, year
        """
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict[str, Any]] = []

        # RT search uses search-page-media-row custom elements
        for item in soup.select("search-page-media-row"):
            parsed = self._extract_search_item(item)
            if parsed and parsed.get("url"):
                results.append(parsed)

        # Limit to top 10
        return results[:10]

    def _extract_search_item(self, item: Tag) -> dict[str, Any] | None:
        """Extract data from a single search result element.

        Args:
            item: BeautifulSoup Tag element

        Returns:
            Dict with url, title, year or None
        """
        try:
            result = self._parse_search_item_data(item)
        except (ValueError, AttributeError):
            result = None

        return result

    @staticmethod
    def _parse_search_item_data(item: Tag) -> dict[str, Any] | None:
        """Parse data from search item tag.

        Args:
            item: BeautifulSoup Tag element

        Returns:
            Dict with url, title, year or None if invalid
        """
        link = item.select_one("a[data-qa='info-name']")
        if not link:
            return None

        href = link.get("href", "")
        if not href.startswith("/m/"):
            return None

        year_str = item.get("releaseyear", "")
        year = int(year_str) if year_str and str(year_str).isdigit() else None
        title_text = link.get_text(strip=True)

        return {"url": href, "title": title_text, "year": year}

    def _find_best_match(
        self,
        results: list[dict[str, Any]],
        year: int | None,
    ) -> str | None:
        """
        Find best matching result with year validation.

        Args:
            results: List of search results
            year: Expected release year

        Returns:
            Best matching URL or None
        """
        if not results:
            return None

        # Priority 1: Exact year match
        if year:
            for result in results:
                rt_year = result.get("year")
                if rt_year and abs(rt_year - year) <= YEAR_TOLERANCE:
                    self.logger.info(f"✅ RT match (year={rt_year}): {result['url']}")
                    return result["url"]

        # Priority 2: First result fallback
        first = results[0]
        self.logger.info(f"✅ RT fallback match: {first['url']}")
        return first["url"]

    # =========================================================================
    # URL VARIANT FALLBACK
    # =========================================================================

    async def _try_url_variants(
        self,
        crawler: AsyncWebCrawler,
        title: str,
        original_title: str | None,
        year: int | None,
    ) -> str | None:
        """
        Try multiple URL variants via direct access.

        Args:
            crawler: AsyncWebCrawler instance
            title: Primary title
            original_title: Alternative title
            year: Release year

        Returns:
            Valid URL if found, None otherwise
        """
        # Generate variants for primary title
        variants = RTUrlBuilder.generate_url_variants(title, year)

        # Add original title variants if different
        if original_title and original_title.lower() != title.lower():
            variants.extend(RTUrlBuilder.generate_url_variants(original_title, year))

        # Test each variant
        for film_url in variants:
            if await self._check_url_valid(crawler, film_url):
                self.logger.info(f"✅ URL variant valid: {film_url}")
                return film_url

        return None

    async def _check_url_valid(self, crawler: AsyncWebCrawler, film_url: str) -> bool:
        """Check if a film URL returns a valid page.

        Args:
            crawler: AsyncWebCrawler instance
            film_url: Relative URL to check

        Returns:
            True if page exists and is valid
        """
        full_url = f"{self.base_url}{film_url}"
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=20000,
        )

        try:
            await asyncio.sleep(random.uniform(0.8, 2.0))
            result = await crawler.arun(url=full_url, config=run_config)
            is_valid = self._is_valid_film_page(result)

        except (TimeoutError, ConnectionError):
            is_valid = False

        return is_valid

    @staticmethod
    def _is_valid_film_page(result: CrawlResult) -> bool:
        """Validate crawl result is a valid film page.

        Args:
            result: Crawl result object.

        Returns:
            True if valid film page.
        """
        if not result.success or not result.html:
            return False

        is_not_404 = "404 - Not Found" not in result.html
        has_scorecard = "media-scorecard-json" in result.html

        return is_not_404 and has_scorecard
