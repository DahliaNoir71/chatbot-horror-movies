"""Rotten Tomatoes extractor package.

Provides web scraping of Rotten Tomatoes for film
score enrichment using Crawl4AI.

Classes:
    RTExtractor: Main extractor orchestrating the process.
    RTScraper: Web scraper using Crawl4AI and BeautifulSoup.
    RTNormalizer: Data transformation to normalized format.
    RTUrlBuilder: URL generation and slug handling.

Usage:
    from src.etl.extractors.rotten_tomatoes import RTExtractor

    extractor = RTExtractor()

    # Single film
    data = await extractor.extract_film("The Shining", year=1980)

    # Batch enrichment
    films = [{"id": 1, "title": "The Shining", "year": 1980}]
    result = await extractor.extract_async(films=films)
"""

from src.etl.extractors.rotten_tomatoes.normalizer import RTNormalizer
from src.etl.extractors.rotten_tomatoes.rotten_tomatoes import RTExtractor
from src.etl.extractors.rotten_tomatoes.scraper import RTScraper
from src.etl.extractors.rotten_tomatoes.url_builder import RTUrlBuilder

__all__ = [
    "RTExtractor",
    "RTScraper",
    "RTNormalizer",
    "RTUrlBuilder",
]
