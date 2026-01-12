"""Rotten Tomatoes URL builder.

Generates URL variants for film pages based on title
and year, handling RT's inconsistent slug formats.
"""

import re
from urllib.parse import quote_plus


class RTUrlBuilder:
    """Builds and generates URL variants for Rotten Tomatoes."""

    BASE_URL = "https://www.rottentomatoes.com"

    # -------------------------------------------------------------------------
    # Search URL
    # -------------------------------------------------------------------------

    @classmethod
    def build_search_url(cls, title: str, year: int | None = None) -> str:
        """Build search page URL.

        Args:
            title: Film title to search.
            year: Optional release year.

        Returns:
            Complete search URL.
        """
        query = f"{title} {year}" if year else title
        encoded = quote_plus(query)
        return f"{cls.BASE_URL}/search?search={encoded}"

    # -------------------------------------------------------------------------
    # Slug Generation
    # -------------------------------------------------------------------------

    @classmethod
    def build_slug(cls, title: str) -> str:
        """Build basic slug from title.

        RT uses underscores, lowercase, no special chars.

        Args:
            title: Film title.

        Returns:
            URL slug (without /m/ prefix).
        """
        slug = title.lower()

        # Remove common articles at start
        slug = re.sub(r"^(the|a|an)\s+", "", slug)

        # Replace special characters
        # Remove apostrophes
        slug = slug.replace("'", "")
        # & -> and
        slug = slug.replace("&", "and")
        # Remove other special chars
        slug = re.sub(r"[^\w\s-]", "", slug)

        # Replace spaces/hyphens with underscores
        slug = re.sub(r"[-\s]+", "_", slug)

        # Clean up multiple underscores
        slug = re.sub(r"_+", "_", slug)

        # Remove leading/trailing underscores
        slug = slug.strip("_")

        return slug

    @classmethod
    def build_film_url(cls, title: str) -> str:
        """Build relative film URL.

        Args:
            title: Film title.

        Returns:
            Relative URL like /m/the_shining.
        """
        slug = cls.build_slug(title)
        return f"/m/{slug}"

    @classmethod
    def build_full_url(cls, relative_url: str) -> str:
        """Build full URL from relative path.

        Args:
            relative_url: Relative URL starting with /.

        Returns:
            Complete URL.
        """
        if relative_url.startswith("http"):
            return relative_url
        return f"{cls.BASE_URL}{relative_url}"

    # -------------------------------------------------------------------------
    # URL Variants
    # -------------------------------------------------------------------------

    @classmethod
    def generate_url_variants(
        cls,
        title: str,
        year: int | None = None,
    ) -> list[str]:
        """Generate multiple URL variants for fallback attempts.

        RT uses inconsistent slug formats:
        - /m/alien_covenant
        - /m/alien_covenant_2017
        - /m/1155109-hoodwinked

        Args:
            title: Film title.
            year: Optional release year.

        Returns:
            List of relative URLs to try.
        """
        variants: list[str] = []
        base_slug = cls.build_slug(title)

        # Variant 1: Basic slug
        variants.append(f"/m/{base_slug}")

        # Variant 2: With year suffix
        if year:
            variants.append(f"/m/{base_slug}_{year}")

        # Variant 3: Keep "the" prefix
        if title.lower().startswith("the "):
            slug_with_the = cls.build_slug(f"the_{title[4:]}")
            variants.append(f"/m/{slug_with_the}")
            if year:
                variants.append(f"/m/{slug_with_the}_{year}")

        # Variant 4: Roman numerals to digits
        roman_map = {
            " ii": "_2",
            " iii": "_3",
            " iv": "_4",
            " v": "_5",
            " vi": "_6",
            " vii": "_7",
            " viii": "_8",
        }
        for roman, digit in roman_map.items():
            if roman in title.lower():
                roman_slug = base_slug.replace(roman.strip(), digit)
                variants.append(f"/m/{roman_slug}")

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique.append(v)

        return unique

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @classmethod
    def is_valid_film_url(cls, url: str) -> bool:
        """Check if URL is a valid RT film URL.

        Args:
            url: URL to validate.

        Returns:
            True if valid film URL.
        """
        return url.startswith("/m/") or url.startswith(f"{cls.BASE_URL}/m/")

    @classmethod
    def extract_slug(cls, url: str) -> str | None:
        """Extract slug from film URL.

        Args:
            url: Film URL.

        Returns:
            Slug or None if invalid.
        """
        match = re.search(r"/m/([^/?#]+)", url)
        return match.group(1) if match else None
