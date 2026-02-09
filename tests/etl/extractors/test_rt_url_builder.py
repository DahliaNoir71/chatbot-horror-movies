"""Unit tests for Rotten Tomatoes URL builder."""

from src.etl.extractors.rotten_tomatoes.url_builder import RTUrlBuilder


class TestBuildSearchUrl:
    @staticmethod
    def test_basic_search() -> None:
        url = RTUrlBuilder.build_search_url("The Shining")
        assert url == "https://www.rottentomatoes.com/search?search=The+Shining"

    @staticmethod
    def test_search_with_year() -> None:
        url = RTUrlBuilder.build_search_url("The Shining", year=1980)
        assert url == "https://www.rottentomatoes.com/search?search=The+Shining+1980"

    @staticmethod
    def test_special_chars_encoded() -> None:
        url = RTUrlBuilder.build_search_url("A&B: Film")
        assert "A%26B" in url


class TestBuildSlug:
    @staticmethod
    def test_basic_slug() -> None:
        assert RTUrlBuilder.build_slug("Alien") == "alien"

    @staticmethod
    def test_removes_the_prefix() -> None:
        assert RTUrlBuilder.build_slug("The Shining") == "shining"

    @staticmethod
    def test_removes_a_prefix() -> None:
        assert RTUrlBuilder.build_slug("A Quiet Place") == "quiet_place"

    @staticmethod
    def test_removes_an_prefix() -> None:
        assert RTUrlBuilder.build_slug("An American Werewolf") == "american_werewolf"

    @staticmethod
    def test_removes_apostrophes() -> None:
        assert RTUrlBuilder.build_slug("It's Alive") == "its_alive"

    @staticmethod
    def test_ampersand_to_and() -> None:
        assert RTUrlBuilder.build_slug("Hansel & Gretel") == "hansel_and_gretel"

    @staticmethod
    def test_hyphens_to_underscores() -> None:
        assert RTUrlBuilder.build_slug("Spider-Man") == "spider_man"

    @staticmethod
    def test_special_chars_removed() -> None:
        slug = RTUrlBuilder.build_slug("Film! (2024)")
        assert "!" not in slug
        assert "(" not in slug

    @staticmethod
    def test_multiple_spaces_collapsed() -> None:
        assert RTUrlBuilder.build_slug("word   word") == "word_word"

    @staticmethod
    def test_no_trailing_underscores() -> None:
        slug = RTUrlBuilder.build_slug("  Film  ")
        assert not slug.startswith("_")
        assert not slug.endswith("_")


class TestBuildFilmUrl:
    @staticmethod
    def test_basic() -> None:
        assert RTUrlBuilder.build_film_url("Alien") == "/m/alien"

    @staticmethod
    def test_with_the() -> None:
        assert RTUrlBuilder.build_film_url("The Shining") == "/m/shining"


class TestBuildFullUrl:
    @staticmethod
    def test_relative_url() -> None:
        result = RTUrlBuilder.build_full_url("/m/alien")
        assert result == "https://www.rottentomatoes.com/m/alien"

    @staticmethod
    def test_absolute_url_passthrough() -> None:
        url = "https://www.rottentomatoes.com/m/alien"
        assert RTUrlBuilder.build_full_url(url) == url


class TestGenerateUrlVariants:
    @staticmethod
    def test_basic_single_variant() -> None:
        variants = RTUrlBuilder.generate_url_variants("Alien")
        assert "/m/alien" in variants

    @staticmethod
    def test_with_year_adds_suffix() -> None:
        variants = RTUrlBuilder.generate_url_variants("Alien", year=1979)
        assert "/m/alien_1979" in variants

    @staticmethod
    def test_the_prefix_variant() -> None:
        variants = RTUrlBuilder.generate_url_variants("The Shining")
        assert "/m/shining" in variants
        assert any("the" in v for v in variants)

    @staticmethod
    def test_the_with_year() -> None:
        variants = RTUrlBuilder.generate_url_variants("The Shining", year=1980)
        assert "/m/shining_1980" in variants

    @staticmethod
    def test_roman_numeral_ii() -> None:
        variants = RTUrlBuilder.generate_url_variants("Aliens II")
        assert any("_2" in v for v in variants)

    @staticmethod
    def test_roman_numeral_iii() -> None:
        variants = RTUrlBuilder.generate_url_variants("Scream III")
        assert any("_3" in v for v in variants)

    @staticmethod
    def test_no_duplicates() -> None:
        variants = RTUrlBuilder.generate_url_variants("Alien")
        assert len(variants) == len(set(variants))

    @staticmethod
    def test_without_year_no_year_suffix() -> None:
        variants = RTUrlBuilder.generate_url_variants("Alien")
        assert all("_19" not in v and "_20" not in v for v in variants)


class TestIsValidFilmUrl:
    @staticmethod
    def test_relative_valid() -> None:
        assert RTUrlBuilder.is_valid_film_url("/m/alien") is True

    @staticmethod
    def test_absolute_valid() -> None:
        url = "https://www.rottentomatoes.com/m/alien"
        assert RTUrlBuilder.is_valid_film_url(url) is True

    @staticmethod
    def test_invalid_path() -> None:
        assert RTUrlBuilder.is_valid_film_url("/tv/series") is False

    @staticmethod
    def test_random_string() -> None:
        assert RTUrlBuilder.is_valid_film_url("not_a_url") is False


class TestExtractSlug:
    @staticmethod
    def test_relative_url() -> None:
        assert RTUrlBuilder.extract_slug("/m/alien") == "alien"

    @staticmethod
    def test_absolute_url() -> None:
        url = "https://www.rottentomatoes.com/m/the_shining"
        assert RTUrlBuilder.extract_slug(url) == "the_shining"

    @staticmethod
    def test_url_with_query() -> None:
        assert RTUrlBuilder.extract_slug("/m/alien?ref=search") == "alien"

    @staticmethod
    def test_no_match_returns_none() -> None:
        assert RTUrlBuilder.extract_slug("/tv/series") is None

    @staticmethod
    def test_url_with_fragment() -> None:
        assert RTUrlBuilder.extract_slug("/m/alien#reviews") == "alien"
