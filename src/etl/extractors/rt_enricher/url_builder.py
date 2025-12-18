"""URL building utilities for Rotten Tomatoes scraping."""

import re

from unidecode import unidecode


class RTUrlBuilder:
    """Builds RT-compatible URLs from film titles."""

    @staticmethod
    def build_slug(title: str) -> str:
        """
        Build RT-compatible slug from title.

        Args:
            title: Film title to convert

        Returns:
            URL-safe slug string
        """
        if not title or not title.strip():
            return ""

        # Transliterate special characters → ASCII
        slug = unidecode(title).lower()
        # Remove non-alphanumeric (keep spaces/hyphens temporarily)
        slug = re.sub(r"[^\w\s-]", "", slug)
        # Replace spaces/hyphens with underscores
        slug = re.sub(r"[-\s]+", "_", slug)
        return slug.strip("_")

    @classmethod
    def generate_url_variants(cls, title: str, year: int | None = None) -> list[str]:
        """
        Generate multiple URL variants to try.

        Args:
            title: Film title
            year: Release year (optional)

        Returns:
            List of relative URLs to attempt
        """
        slug = cls.build_slug(title)
        if not slug:
            return []

        variants = [f"/m/{slug}"]

        # Add year suffix variant (common RT pattern)
        if year:
            variants.append(f"/m/{slug}_{year}")

        # Handle "The" prefix removal
        if title.lower().startswith("the "):
            slug_no_the = cls.build_slug(title[4:])
            if slug_no_the:
                variants.append(f"/m/{slug_no_the}")
                if year:
                    variants.append(f"/m/{slug_no_the}_{year}")

        return variants

    @staticmethod
    def build_search_url(title: str) -> str:
        """
        Build RT search page URL.

        Args:
            title: Film title to search

        Returns:
            Complete search URL
        """
        query = title.replace(" ", "%20")
        return f"https://www.rottentomatoes.com/search?search={query}"
