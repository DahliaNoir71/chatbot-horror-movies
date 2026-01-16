"""Unit tests for ETL type definitions.

Tests validate TypedDict instantiation and module exports.
"""

from datetime import date
from pytest import approx


class TestModuleExports:
    """Test package exports from __init__.py."""

    @staticmethod
    def test_all_tmdb_types_exported() -> None:
        """Verify TMDB types are exported."""
        from src.etl.types import (
            TMDBCastData,
            TMDBCreditsData,
            TMDBCrewData,
            TMDBDiscoverResponse,
            TMDBFilmData,
            TMDBGenreData,
            TMDBKeywordData,
            TMDBKeywordsResponse,
            TMDBProductionCompanyData,
            TMDBSpokenLanguageData,
        )

        assert TMDBFilmData is not None
        assert TMDBGenreData is not None
        assert TMDBKeywordData is not None
        assert TMDBCastData is not None
        assert TMDBCrewData is not None
        assert TMDBCreditsData is not None
        assert TMDBProductionCompanyData is not None
        assert TMDBSpokenLanguageData is not None
        assert TMDBDiscoverResponse is not None
        assert TMDBKeywordsResponse is not None

    @staticmethod
    def test_all_rt_types_exported() -> None:
        """Verify Rotten Tomatoes types are exported."""
        from src.etl.types import RTMoviePageData, RTScoreData, RTSearchResult

        assert RTScoreData is not None
        assert RTSearchResult is not None
        assert RTMoviePageData is not None

    @staticmethod
    def test_all_kaggle_types_exported() -> None:
        """Verify Kaggle types are exported."""
        from src.etl.types import (
            KaggleEnrichmentStats,
            KaggleExtractionResult,
            KaggleHorrorMovieNormalized,
            KaggleHorrorMovieRaw,
        )

        assert KaggleHorrorMovieRaw is not None
        assert KaggleHorrorMovieNormalized is not None
        assert KaggleExtractionResult is not None
        assert KaggleEnrichmentStats is not None

    @staticmethod
    def test_all_normalized_types_exported() -> None:
        """Verify normalized types are exported."""
        from src.etl.types import (
            NormalizedCompanyData,
            NormalizedCreditData,
            NormalizedFilmData,
            NormalizedGenreData,
            NormalizedKeywordData,
            NormalizedLanguageData,
            NormalizedRTScoreData,
        )

        assert NormalizedFilmData is not None
        assert NormalizedCreditData is not None
        assert NormalizedGenreData is not None
        assert NormalizedKeywordData is not None
        assert NormalizedRTScoreData is not None
        assert NormalizedCompanyData is not None
        assert NormalizedLanguageData is not None

    @staticmethod
    def test_all_pipeline_types_exported() -> None:
        """Verify pipeline types are exported."""
        from src.etl.types import (
            CreditLoadInput,
            ETLCheckpoint,
            ETLPipelineStats,
            ETLProgress,
            ETLResult,
            ETLRunConfig,
            ExtractionStats,
            FilmMatchCandidate,
            FilmMatchResult,
            FilmToEnrich,
            LoadStats,
            TransformationStats,
        )

        assert ETLResult is not None
        assert ETLCheckpoint is not None
        assert ETLRunConfig is not None
        assert ETLProgress is not None
        assert ETLPipelineStats is not None
        assert ExtractionStats is not None
        assert TransformationStats is not None
        assert LoadStats is not None
        assert FilmMatchResult is not None
        assert FilmMatchCandidate is not None
        assert CreditLoadInput is not None
        assert FilmToEnrich is not None


class TestTMDBTypes:
    """Test TMDB TypedDict instantiation."""

    @staticmethod
    def test_tmdb_genre_data() -> None:
        """Test TMDBGenreData creation."""
        from src.etl.types.tmdb import TMDBGenreData

        genre: TMDBGenreData = {"id": 27, "name": "Horror"}
        assert genre["id"] == 27
        assert genre["name"] == "Horror"

    @staticmethod
    def test_tmdb_keyword_data() -> None:
        """Test TMDBKeywordData creation."""
        from src.etl.types.tmdb import TMDBKeywordData

        keyword: TMDBKeywordData = {"id": 1234, "name": "zombie"}
        assert keyword["id"] == 1234

    @staticmethod
    def test_tmdb_cast_data_minimal() -> None:
        """Test TMDBCastData with required fields."""
        from src.etl.types.tmdb import TMDBCastData

        cast: TMDBCastData = {
            "id": 1,
            "name": "Actor Name",
            "character": "Character",
            "order": 0,
        }
        assert cast["name"] == "Actor Name"

    @staticmethod
    def test_tmdb_cast_data_full() -> None:
        """Test TMDBCastData with all fields."""
        from src.etl.types.tmdb import TMDBCastData

        cast: TMDBCastData = {
            "id": 1,
            "name": "Actor",
            "character": "Role",
            "order": 0,
            "profile_path": "/path.jpg",
        }
        assert cast["profile_path"] == "/path.jpg"

    @staticmethod
    def test_tmdb_crew_data() -> None:
        """Test TMDBCrewData creation."""
        from src.etl.types.tmdb import TMDBCrewData

        crew: TMDBCrewData = {
            "id": 1,
            "name": "Director",
            "department": "Directing",
            "job": "Director",
        }
        assert crew["department"] == "Directing"

    @staticmethod
    def test_tmdb_credits_data() -> None:
        """Test TMDBCreditsData creation."""
        from src.etl.types.tmdb import TMDBCreditsData

        film_credits: TMDBCreditsData = {"cast": [], "crew": []}
        assert isinstance(film_credits["cast"], list)

    @staticmethod
    def test_tmdb_film_data_minimal() -> None:
        """Test TMDBFilmData with required fields only."""
        from src.etl.types.tmdb import TMDBFilmData

        film: TMDBFilmData = {
            "id": 123,
            "title": "Horror Movie",
            "overview": "A scary film",
            "release_date": "2024-01-01",
            "popularity": 10.5,
            "vote_average": 7.5,
            "vote_count": 100,
            "adult": False,
            "genre_ids": [27],
        }
        assert film["title"] == "Horror Movie"

    @staticmethod
    def test_tmdb_film_data_full() -> None:
        """Test TMDBFilmData with all fields."""
        from src.etl.types.tmdb import TMDBFilmData

        film: TMDBFilmData = {
            "id": 123,
            "title": "Horror Movie",
            "overview": "Scary",
            "release_date": "2024-01-01",
            "popularity": 10.5,
            "vote_average": 7.5,
            "vote_count": 100,
            "adult": False,
            "genre_ids": [27],
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "imdb_id": "tt1234567",
            "original_title": "Original",
            "original_language": "en",
            "tagline": "Be afraid",
            "runtime": 120,
            "status": "Released",
            "homepage": "https://example.com",
            "budget": 1000000,
            "revenue": 5000000,
            "genres": [{"id": 27, "name": "Horror"}],
            "keywords": [],
            "credits": {"cast": [], "crew": []},
            "production_companies": [],
            "spoken_languages": [],
        }
        assert film["imdb_id"] == "tt1234567"

    @staticmethod
    def test_tmdb_discover_response() -> None:
        """Test TMDBDiscoverResponse creation."""
        from src.etl.types.tmdb import TMDBDiscoverResponse

        response: TMDBDiscoverResponse = {
            "page": 1,
            "total_pages": 10,
            "total_results": 200,
            "results": [],
        }
        assert response["total_pages"] == 10

    @staticmethod
    def test_tmdb_keywords_response() -> None:
        """Test TMDBKeywordsResponse creation."""
        from src.etl.types.tmdb import TMDBKeywordsResponse

        response: TMDBKeywordsResponse = {
            "id": 123,
            "keywords": [{"id": 1, "name": "horror"}],
        }
        assert len(response["keywords"]) == 1


class TestRottenTomatoesTypes:
    """Test Rotten Tomatoes TypedDict instantiation."""

    @staticmethod
    def test_rt_score_data_minimal() -> None:
        """Test RTScoreData with minimal fields."""
        from src.etl.types.rotten_tomatoes import RTScoreData

        score: RTScoreData = {
            "tomatometer_score": 85,
            "audience_score": 75,
        }
        assert score["tomatometer_score"] == 85

    @staticmethod
    def test_rt_score_data_full() -> None:
        """Test RTScoreData with all fields."""
        from src.etl.types.rotten_tomatoes import RTScoreData

        score: RTScoreData = {
            "film_id": 1,
            "tmdb_id": 123,
            "tomatometer_score": 85,
            "tomatometer_state": "certified-fresh",
            "critics_count": 200,
            "critics_average_rating": 7.5,
            "audience_score": 75,
            "audience_state": "upright",
            "audience_count": 5000,
            "audience_average_rating": 3.8,
            "critics_consensus": "A terrifying masterpiece.",
            "rt_url": "https://rottentomatoes.com/m/movie",
            "rt_rating": "R",
        }
        assert score["critics_consensus"] == "A terrifying masterpiece."

    @staticmethod
    def test_rt_search_result() -> None:
        """Test RTSearchResult creation."""
        from src.etl.types.rotten_tomatoes import RTSearchResult

        result: RTSearchResult = {
            "title": "Horror Film",
            "year": 2024,
            "url": "/m/horror_film",
            "tomatometer_score": 90,
        }
        assert result["url"] == "/m/horror_film"

    @staticmethod
    def test_rt_movie_page_data() -> None:
        """Test RTMoviePageData creation."""
        from src.etl.types.rotten_tomatoes import RTMoviePageData

        page: RTMoviePageData = {
            "title": "Horror Film",
            "rt_url": "https://rt.com/m/film",
            "tomatometer_score": 85,
            "tomatometer_state": "fresh",
            "audience_score": 70,
            "audience_state": "upright",
            "critics_count": 100,
            "audience_count": 1000,
            "critics_average_rating": 7.0,
            "audience_average_rating": 3.5,
            "critics_consensus": "Scary good.",
            "rt_rating": "R",
        }
        assert page["tomatometer_state"] == "fresh"


class TestKaggleTypes:
    """Test Kaggle TypedDict instantiation."""

    @staticmethod
    def test_kaggle_raw_minimal() -> None:
        """Test KaggleHorrorMovieRaw with required field."""
        from src.etl.types.kaggle import KaggleHorrorMovieRaw

        raw: KaggleHorrorMovieRaw = {"id": 123}
        assert raw["id"] == 123

    @staticmethod
    def test_kaggle_raw_full() -> None:
        """Test KaggleHorrorMovieRaw with all fields."""
        from src.etl.types.kaggle import KaggleHorrorMovieRaw

        raw: KaggleHorrorMovieRaw = {
            "id": 123,
            "title": "Horror Movie",
            "original_title": "Original",
            "original_language": "en",
            "overview": "Synopsis",
            "tagline": "Tagline",
            "release_date": "2024-01-01",
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "popularity": 10.5,
            "vote_average": 7.5,
            "vote_count": 100,
            "budget": 1000000,
            "revenue": 5000000,
            "runtime": 90,
            "status": "Released",
            "adult": False,
            "genre_names": "Horror, Thriller",
            "collection_name": "Franchise",
        }
        assert raw["genre_names"] == "Horror, Thriller"

    @staticmethod
    def test_kaggle_normalized() -> None:
        """Test KaggleHorrorMovieNormalized creation."""
        from src.etl.types.kaggle import KaggleHorrorMovieNormalized

        normalized: KaggleHorrorMovieNormalized = {
            "tmdb_id": 123,
            "title": "Horror",
            "original_title": None,
            "original_language": "en",
            "overview": None,
            "tagline": None,
            "poster_path": None,
            "backdrop_path": None,
            "popularity": 10.0,
            "vote_average": 7.0,
            "vote_count": 100,
            "budget": 0,
            "revenue": 0,
            "runtime": 90,
            "status": "Released",
            "adult": False,
            "source": "kaggle",
        }
        assert normalized["source"] == "kaggle"

    @staticmethod
    def test_kaggle_extraction_result() -> None:
        """Test KaggleExtractionResult creation."""
        from src.etl.types.kaggle import KaggleExtractionResult

        result: KaggleExtractionResult = {
            "total_rows": 1000,
            "valid_rows": 950,
            "skipped_rows": 50,
            "error_count": 5,
            "duration_seconds": 1.5,
        }
        assert result["valid_rows"] == 950

    @staticmethod
    def test_kaggle_enrichment_stats() -> None:
        """Test KaggleEnrichmentStats creation."""
        from src.etl.types.kaggle import KaggleEnrichmentStats

        stats: KaggleEnrichmentStats = {
            "films_enriched": 100,
            "films_inserted": 50,
            "budget_updates": 30,
            "revenue_updates": 25,
            "skipped": 10,
            "errors": 2,
        }
        assert stats["films_enriched"] == 100


class TestNormalizedTypes:
    """Test normalized TypedDict instantiation."""

    @staticmethod
    def test_normalized_film_data() -> None:
        """Test NormalizedFilmData creation."""
        from src.etl.types.normalized import NormalizedFilmData

        film: NormalizedFilmData = {
            "tmdb_id": 123,
            "imdb_id": "tt1234567",
            "title": "Horror",
            "original_title": None,
            "release_date": date(2024, 1, 1),
            "tagline": None,
            "overview": "Synopsis",
            "popularity": 10.0,
            "vote_average": 7.0,
            "vote_count": 100,
            "runtime": 90,
            "original_language": "en",
            "status": "Released",
            "adult": False,
            "poster_path": None,
            "backdrop_path": None,
            "homepage": None,
            "budget": 0,
            "revenue": 0,
            "source": "tmdb",
        }
        assert film["tmdb_id"] == 123

    @staticmethod
    def test_normalized_credit_data() -> None:
        """Test NormalizedCreditData creation."""
        from src.etl.types.normalized import NormalizedCreditData

        credit: NormalizedCreditData = {
            "tmdb_person_id": 1,
            "person_name": "Actor",
            "role_type": "cast",
            "character_name": "Character",
            "department": None,
            "job": None,
            "display_order": 0,
            "profile_path": None,
        }
        assert credit["role_type"] == "cast"

    @staticmethod
    def test_normalized_genre_data() -> None:
        """Test NormalizedGenreData creation."""
        from src.etl.types.normalized import NormalizedGenreData

        genre: NormalizedGenreData = {"tmdb_genre_id": 27, "name": "Horror"}
        assert genre["name"] == "Horror"

    @staticmethod
    def test_normalized_keyword_data() -> None:
        """Test NormalizedKeywordData creation."""
        from src.etl.types.normalized import NormalizedKeywordData

        keyword: NormalizedKeywordData = {"tmdb_keyword_id": 123, "name": "zombie"}
        assert keyword["name"] == "zombie"

    @staticmethod
    def test_normalized_rt_score_data() -> None:
        """Test NormalizedRTScoreData creation."""
        from src.etl.types.normalized import NormalizedRTScoreData

        score: NormalizedRTScoreData = {
            "film_id": 1,
            "tomatometer_score": 85,
            "tomatometer_state": "fresh",
            "critics_count": 100,
            "critics_average_rating": 7.5,
            "audience_score": 70,
            "audience_state": "upright",
            "audience_count": 1000,
            "audience_average_rating": 3.5,
            "critics_consensus": "Great film.",
            "rt_url": "https://rt.com/m/film",
            "rt_rating": "R",
        }
        assert score["film_id"] == 1

    @staticmethod
    def test_normalized_company_data() -> None:
        """Test NormalizedCompanyData creation."""
        from src.etl.types.normalized import NormalizedCompanyData

        company: NormalizedCompanyData = {
            "tmdb_company_id": 1,
            "name": "Studio",
            "origin_country": "US",
        }
        assert company["name"] == "Studio"

    @staticmethod
    def test_normalized_language_data() -> None:
        """Test NormalizedLanguageData creation."""
        from src.etl.types.normalized import NormalizedLanguageData

        lang: NormalizedLanguageData = {"iso_639_1": "en", "name": "English"}
        assert lang["iso_639_1"] == "en"


class TestPipelineTypes:
    """Test pipeline TypedDict instantiation."""

    @staticmethod
    def test_etl_result_minimal() -> None:
        """Test ETLResult with required fields."""
        from src.etl.types.pipeline import ETLResult

        result: ETLResult = {"source": "tmdb", "success": True, "count": 100}
        assert result["success"] is True

    @staticmethod
    def test_etl_result_full() -> None:
        """Test ETLResult with all fields."""
        from src.etl.types.pipeline import ETLResult

        result: ETLResult = {
            "source": "tmdb",
            "success": False,
            "count": 0,
            "errors": ["Connection failed"],
            "duration_seconds": 5.5,
        }
        assert len(result["errors"]) == 1

    @staticmethod
    def test_etl_checkpoint() -> None:
        """Test ETLCheckpoint creation."""
        from src.etl.types.pipeline import ETLCheckpoint

        checkpoint: ETLCheckpoint = {
            "source": "tmdb",
            "last_page": 5,
            "last_year": 2024,
            "timestamp": "2024-01-01T00:00:00",
        }
        assert checkpoint["last_page"] == 5

    @staticmethod
    def test_etl_run_config() -> None:
        """Test ETLRunConfig creation."""
        from src.etl.types.pipeline import ETLRunConfig

        config: ETLRunConfig = {
            "sources": ["tmdb", "rt"],
            "year_min": 2020,
            "year_max": 2024,
            "max_films": 1000,
            "enrich": True,
            "resume": False,
        }
        assert "tmdb" in config["sources"]

    @staticmethod
    def test_etl_progress() -> None:
        """Test ETLProgress creation."""
        from src.etl.types.pipeline import ETLProgress

        progress: ETLProgress = {
            "source": "tmdb",
            "current": 50,
            "total": 100,
            "percentage": 50.0,
            "elapsed_seconds": 10.0,
            "eta_seconds": 10.0,
        }
        assert progress["percentage"] == approx(50.0)

    @staticmethod
    def test_film_match_result() -> None:
        """Test FilmMatchResult creation."""
        from src.etl.types.pipeline import FilmMatchResult

        match: FilmMatchResult = {
            "film_id": 1,
            "video_id": 100,
            "match_score": 0.95,
            "match_method": "title_year",
            "matched_title": "Horror Film",
        }
        assert match["match_score"] == approx(0.95)

    @staticmethod
    def test_film_match_candidate() -> None:
        """Test FilmMatchCandidate creation."""
        from src.etl.types.pipeline import FilmMatchCandidate

        candidate: FilmMatchCandidate = {
            "film_id": 1,
            "title": "Horror",
            "year": 2024,
            "score": 0.9,
        }
        assert candidate["year"] == 2024

    @staticmethod
    def test_extraction_stats() -> None:
        """Test ExtractionStats creation."""
        from src.etl.types.pipeline import ExtractionStats

        stats: ExtractionStats = {
            "total_extracted": 1000,
            "new_records": 800,
            "updated_records": 150,
            "skipped": 50,
            "errors": 5,
            "duration_seconds": 30.0,
        }
        assert stats["new_records"] == 800

    @staticmethod
    def test_transformation_stats() -> None:
        """Test TransformationStats creation."""
        from src.etl.types.pipeline import TransformationStats

        stats: TransformationStats = {
            "total_processed": 1000,
            "valid": 950,
            "invalid": 30,
            "cleaned": 20,
            "duration_seconds": 5.0,
        }
        assert stats["valid"] == 950

    @staticmethod
    def test_load_stats() -> None:
        """Test LoadStats creation."""
        from src.etl.types.pipeline import LoadStats

        stats: LoadStats = {
            "total_loaded": 950,
            "inserted": 800,
            "updated": 150,
            "failed": 5,
            "duration_seconds": 10.0,
        }
        assert stats["inserted"] == 800

    @staticmethod
    def test_etl_pipeline_stats() -> None:
        """Test ETLPipelineStats creation."""
        from src.etl.types.pipeline import ETLPipelineStats

        stats: ETLPipelineStats = {
            "run_id": "run-123",
            "started_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T01:00:00",
            "status": "completed",
            "total_duration_seconds": 3600.0,
        }
        assert stats["status"] == "completed"

    @staticmethod
    def test_credit_load_input() -> None:
        """Test CreditLoadInput creation."""
        from src.etl.types.pipeline import CreditLoadInput

        input_data: CreditLoadInput = {"credits": [], "film_id": 1}
        assert input_data["film_id"] == 1

    @staticmethod
    def test_film_to_enrich() -> None:
        """Test FilmToEnrich creation."""
        from src.etl.types.pipeline import FilmToEnrich

        film: FilmToEnrich = {
            "id": 1,
            "title": "Horror",
            "original_title": None,
            "year": 2024,
        }
        assert film["id"] == 1


class TestSparkTypes:
    """Test Spark TypedDict instantiation."""

    @staticmethod
    def test_spark_raw_movie() -> None:
        """Test SparkRawMovie creation (total=False)."""
        from src.etl.types.spark import SparkRawMovie

        movie: SparkRawMovie = {"id": 123, "title": "Horror"}
        assert movie["id"] == 123

    @staticmethod
    def test_spark_enriched_movie() -> None:
        """Test SparkEnrichedMovie creation."""
        from src.etl.types.spark import SparkEnrichedMovie

        movie: SparkEnrichedMovie = {
            "kaggle_id": 123,
            "title": "Horror",
            "release_year": 2024,
            "decade": 2020,
            "rating": 7.5,
            "rating_category": "high",
            "global_rank": 1,
        }
        assert movie["decade"] == 2020

    @staticmethod
    def test_spark_normalized() -> None:
        """Test SparkNormalized creation."""
        from src.etl.types.spark import SparkNormalized

        normalized: SparkNormalized = {
            "kaggle_id": 123,
            "title": "Horror",
            "release_year": 2024,
            "decade": 2020,
            "rating": 7.5,
            "votes": 100,
            "popularity": 10.0,
            "runtime": 90,
            "overview": "Synopsis",
            "genre_names": "Horror",
            "rating_category": "high",
            "source": "spark",
        }
        assert normalized["source"] == "spark"

    @staticmethod
    def test_spark_decade_stats() -> None:
        """Test SparkDecadeStats creation."""
        from src.etl.types.spark import SparkDecadeStats

        stats: SparkDecadeStats = {
            "decade": 2020,
            "movie_count": 100,
            "avg_rating": 6.5,
            "avg_votes": 500.0,
            "avg_popularity": 15.0,
            "min_rating": 2.0,
            "max_rating": 9.5,
        }
        assert stats["decade"] == 2020

    @staticmethod
    def test_spark_language_stats() -> None:
        """Test SparkLanguageStats creation."""
        from src.etl.types.spark import SparkLanguageStats

        stats: SparkLanguageStats = {
            "original_language": "en",
            "movie_count": 500,
            "avg_rating": 6.8,
            "high_rated_count": 100,
            "high_rated_pct": 20.0,
        }
        assert stats["original_language"] == "en"

    @staticmethod
    def test_spark_ranked_movie() -> None:
        """Test SparkRankedMovie creation."""
        from src.etl.types.spark import SparkRankedMovie

        movie: SparkRankedMovie = {
            "id": 123,
            "title": "Horror",
            "release_year": 2024,
            "rating": 8.0,
            "votes": 1000,
            "year_rank": 1,
        }
        assert movie["year_rank"] == 1

    @staticmethod
    def test_spark_percentile_movie() -> None:
        """Test SparkPercentileMovie creation."""
        from src.etl.types.spark import SparkPercentileMovie

        movie: SparkPercentileMovie = {
            "id": 123,
            "title": "Horror",
            "rating": 8.5,
            "votes": 2000,
            "percentile": 95.0,
            "quartile": 4,
        }
        assert movie["quartile"] == 4

    @staticmethod
    def test_spark_extraction_result() -> None:
        """Test SparkExtractionResult creation."""
        from src.etl.types.spark import SparkExtractionResult

        result: SparkExtractionResult = {
            "total_rows": 10000,
            "filtered_movies": 5000,
            "exported_count": 4500,
            "duration_seconds": 120.0,
            "export_path": "/data/output.parquet",
        }
        assert result["filtered_movies"] == 5000


class TestIMDBTypes:
    """Test IMDB TypedDict instantiation."""

    @staticmethod
    def test_imdb_title_raw_minimal() -> None:
        """Test IMDBTitleRaw with required fields."""
        from src.etl.types.imdb import IMDBTitleRaw

        title: IMDBTitleRaw = {
            "title_id": "tt0078748",
            "type": "movie",
            "primary_title": "Alien",
        }
        assert title["title_id"] == "tt0078748"

    @staticmethod
    def test_imdb_title_raw_full() -> None:
        """Test IMDBTitleRaw with all fields."""
        from src.etl.types.imdb import IMDBTitleRaw

        title: IMDBTitleRaw = {
            "title_id": "tt0078748",
            "type": "movie",
            "primary_title": "Alien",
            "original_title": "Alien",
            "is_adult": 0,
            "premiered": 1979,
            "ended": None,
            "runtime_minutes": 117,
            "genres": "Horror,Sci-Fi",
        }
        assert title["premiered"] == 1979

    @staticmethod
    def test_imdb_rating_raw() -> None:
        """Test IMDBRatingRaw creation."""
        from src.etl.types.imdb import IMDBRatingRaw

        rating: IMDBRatingRaw = {
            "title_id": "tt0078748",
            "rating": 8.5,
            "votes": 900000,
        }
        assert rating["rating"] == approx(8.5)

    @staticmethod
    def test_imdb_crew_raw() -> None:
        """Test IMDBCrewRaw creation."""
        from src.etl.types.imdb import IMDBCrewRaw

        crew: IMDBCrewRaw = {
            "title_id": "tt0078748",
            "directors": "nm0000631",
            "writers": "nm0649490",
        }
        assert crew["title_id"] == "tt0078748"

    @staticmethod
    def test_imdb_principal_raw() -> None:
        """Test IMDBPrincipalRaw creation."""
        from src.etl.types.imdb import IMDBPrincipalRaw

        principal: IMDBPrincipalRaw = {
            "title_id": "tt0078748",
            "ordering": 1,
            "name_id": "nm0000244",
            "category": "actress",
            "job": None,
            "characters": '["Ellen Ripley"]',
        }
        assert principal["ordering"] == 1

    @staticmethod
    def test_imdb_name_raw() -> None:
        """Test IMDBNameRaw creation."""
        from src.etl.types.imdb import IMDBNameRaw

        name: IMDBNameRaw = {
            "name_id": "nm0000244",
            "primary_name": "Sigourney Weaver",
            "birth_year": 1949,
            "death_year": None,
            "primary_profession": "actress,producer",
            "known_for_titles": "tt0078748,tt0090605",
        }
        assert name["primary_name"] == "Sigourney Weaver"

    @staticmethod
    def test_imdb_horror_movie_joined() -> None:
        """Test IMDBHorrorMovieJoined creation."""
        from src.etl.types.imdb import IMDBHorrorMovieJoined

        movie: IMDBHorrorMovieJoined = {
            "imdb_id": "tt0078748",
            "title": "Alien",
            "original_title": "Alien",
            "year": 1979,
            "runtime": 117,
            "genres": "Horror,Sci-Fi",
            "rating": 8.5,
            "votes": 900000,
            "directors": "nm0000631",
            "writers": "nm0649490",
        }
        assert movie["year"] == 1979

    @staticmethod
    def test_imdb_normalized() -> None:
        """Test IMDBNormalized creation."""
        from src.etl.types.imdb import IMDBNormalized

        normalized: IMDBNormalized = {
            "imdb_id": "tt0078748",
            "imdb_rating": 8.5,
            "imdb_votes": 900000,
            "runtime": 117,
        }
        assert normalized["imdb_rating"] == approx(8.5)

    @staticmethod
    def test_imdb_extraction_result() -> None:
        """Test IMDBExtractionResult creation."""
        from src.etl.types.imdb import IMDBExtractionResult

        result: IMDBExtractionResult = {
            "total_titles": 10000,
            "horror_movies": 2000,
            "with_ratings": 1800,
            "matched_films": 1500,
            "duration_seconds": 45.0,
        }
        assert result["horror_movies"] == 2000

    @staticmethod
    def test_imdb_enrichment_stats() -> None:
        """Test IMDBEnrichmentStats creation."""
        from src.etl.types.imdb import IMDBEnrichmentStats

        stats: IMDBEnrichmentStats = {
            "films_matched": 1500,
            "ratings_updated": 1400,
            "runtime_updated": 200,
            "not_found": 100,
            "errors": 5,
        }
        assert stats["ratings_updated"] == 1400
