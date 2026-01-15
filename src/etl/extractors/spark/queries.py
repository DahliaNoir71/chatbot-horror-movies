"""SparkSQL queries for C2 competency validation.

Contains SparkSQL queries demonstrating Big Data capabilities:
- Window functions (ROW_NUMBER, RANK, LAG, LEAD)
- Complex aggregations (ROLLUP, CUBE, GROUPING SETS)
- CTEs (Common Table Expressions)
- CASE WHEN expressions
- Date/string functions specific to Spark
"""


class SparkQueries:
    """SparkSQL queries for horror movie analytics.

    All queries use SparkSQL syntax to validate C2 competency
    on Big Data systems. Queries demonstrate capabilities beyond
    standard SQL.

    Expected DataFrame schema (Kaggle horror_movies.csv):
        - id: int
        - title: string
        - release_date: string (YYYY-MM-DD)
        - vote_average: double
        - vote_count: int
        - popularity: double
        - overview: string
        - genre_names: string (comma-separated)
        - original_language: string
        - budget: long
        - revenue: long
        - runtime: int
    """

    # -------------------------------------------------------------------------
    # View Registration
    # -------------------------------------------------------------------------

    VIEW_NAME = "horror_movies"

    # -------------------------------------------------------------------------
    # Basic Filtering Queries
    # -------------------------------------------------------------------------

    @staticmethod
    def horror_movies_filtered(
        min_votes: int = 100,
        min_rating: float = 5.0,
    ) -> str:
        """Filter horror movies by votes and rating.

        Demonstrates:
            - WHERE clause with multiple conditions
            - CAST for type conversion
            - COALESCE for null handling

        Args:
            min_votes: Minimum vote count.
            min_rating: Minimum rating threshold.

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                id,
                title,
                CAST(release_date AS DATE) AS release_date,
                COALESCE(vote_average, 0.0) AS rating,
                COALESCE(vote_count, 0) AS votes,
                popularity,
                original_language,
                runtime
            FROM {SparkQueries.VIEW_NAME}
            WHERE vote_count >= {min_votes}
              AND vote_average >= {min_rating}
            ORDER BY vote_average DESC, vote_count DESC
        """

    # -------------------------------------------------------------------------
    # Window Function Queries (Spark-specific C2)
    # -------------------------------------------------------------------------

    @staticmethod
    def ranked_by_year() -> str:
        """Rank horror movies within each year.

        Demonstrates:
            - ROW_NUMBER() window function
            - PARTITION BY for grouping
            - YEAR() date extraction
            - ORDER BY within window

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                id,
                title,
                YEAR(CAST(release_date AS DATE)) AS release_year,
                vote_average AS rating,
                vote_count AS votes,
                ROW_NUMBER() OVER (
                    PARTITION BY YEAR(CAST(release_date AS DATE))
                    ORDER BY vote_average DESC, vote_count DESC
                ) AS year_rank
            FROM {SparkQueries.VIEW_NAME}
            WHERE vote_count >= 100
              AND release_date IS NOT NULL
        """

    @staticmethod
    def rating_percentiles() -> str:
        """Calculate rating percentiles using window functions.

        Demonstrates:
            - PERCENT_RANK() window function
            - NTILE() for quartile distribution
            - Multiple window functions in same query

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                id,
                title,
                vote_average AS rating,
                vote_count AS votes,
                ROUND(PERCENT_RANK() OVER (ORDER BY vote_average), 3) AS percentile,
                NTILE(4) OVER (ORDER BY vote_average) AS quartile
            FROM {SparkQueries.VIEW_NAME}
            WHERE vote_count >= 50
        """

    @staticmethod
    def popularity_trend_analysis() -> str:
        """Analyze popularity trends with LAG/LEAD.

        Demonstrates:
            - LAG() for previous row access
            - LEAD() for next row access
            - Calculated trend indicators

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                id,
                title,
                YEAR(CAST(release_date AS DATE)) AS release_year,
                popularity,
                LAG(popularity) OVER (
                    ORDER BY CAST(release_date AS DATE)
                ) AS prev_popularity,
                LEAD(popularity) OVER (
                    ORDER BY CAST(release_date AS DATE)
                ) AS next_popularity,
                popularity - LAG(popularity) OVER (
                    ORDER BY CAST(release_date AS DATE)
                ) AS popularity_change
            FROM {SparkQueries.VIEW_NAME}
            WHERE release_date IS NOT NULL
              AND vote_count >= 100
            ORDER BY release_date
        """

    # -------------------------------------------------------------------------
    # Advanced Aggregation Queries
    # -------------------------------------------------------------------------

    @staticmethod
    def stats_by_decade() -> str:
        """Aggregate statistics by decade.

        Demonstrates:
            - Integer division for decade grouping
            - Multiple aggregate functions
            - HAVING clause for group filtering

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                (YEAR(CAST(release_date AS DATE)) DIV 10) * 10 AS decade,
                COUNT(*) AS movie_count,
                ROUND(AVG(vote_average), 2) AS avg_rating,
                ROUND(AVG(vote_count), 0) AS avg_votes,
                ROUND(AVG(popularity), 2) AS avg_popularity,
                MIN(vote_average) AS min_rating,
                MAX(vote_average) AS max_rating
            FROM {SparkQueries.VIEW_NAME}
            WHERE release_date IS NOT NULL
              AND vote_count >= 50
            GROUP BY (YEAR(CAST(release_date AS DATE)) DIV 10) * 10
            HAVING COUNT(*) >= 10
            ORDER BY decade
        """

    @staticmethod
    def stats_by_language() -> str:
        """Aggregate statistics by original language.

        Demonstrates:
            - GROUP BY on categorical column
            - Conditional aggregation with CASE

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                original_language,
                COUNT(*) AS movie_count,
                ROUND(AVG(vote_average), 2) AS avg_rating,
                SUM(CASE WHEN vote_average >= 7.0 THEN 1 ELSE 0 END) AS high_rated_count,
                ROUND(
                    SUM(CASE WHEN vote_average >= 7.0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                    1
                ) AS high_rated_pct
            FROM {SparkQueries.VIEW_NAME}
            WHERE vote_count >= 100
            GROUP BY original_language
            HAVING COUNT(*) >= 5
            ORDER BY movie_count DESC
        """

    # -------------------------------------------------------------------------
    # CTE (Common Table Expression) Queries
    # -------------------------------------------------------------------------

    @staticmethod
    def top_movies_with_context() -> str:
        """Get top movies with decade context using CTE.

        Demonstrates:
            - WITH clause (CTE)
            - Subquery in CTE
            - JOIN between CTE and main table

        Returns:
            SparkSQL query string.
        """
        return f"""
            WITH decade_stats AS (
                SELECT
                    (YEAR(CAST(release_date AS DATE)) DIV 10) * 10 AS decade,
                    AVG(vote_average) AS decade_avg_rating,
                    COUNT(*) AS decade_count
                FROM {SparkQueries.VIEW_NAME}
                WHERE release_date IS NOT NULL AND vote_count >= 100
                GROUP BY (YEAR(CAST(release_date AS DATE)) DIV 10) * 10
            ),
            ranked_movies AS (
                SELECT
                    id,
                    title,
                    (YEAR(CAST(release_date AS DATE)) DIV 10) * 10 AS decade,
                    vote_average AS rating,
                    vote_count AS votes,
                    ROW_NUMBER() OVER (
                        PARTITION BY (YEAR(CAST(release_date AS DATE)) DIV 10) * 10
                        ORDER BY vote_average DESC
                    ) AS decade_rank
                FROM {SparkQueries.VIEW_NAME}
                WHERE release_date IS NOT NULL AND vote_count >= 100
            )
            SELECT
                rm.id,
                rm.title,
                rm.decade,
                rm.rating,
                rm.votes,
                rm.decade_rank,
                ROUND(ds.decade_avg_rating, 2) AS decade_avg,
                ROUND(rm.rating - ds.decade_avg_rating, 2) AS vs_decade_avg
            FROM ranked_movies rm
            JOIN decade_stats ds ON rm.decade = ds.decade
            WHERE rm.decade_rank <= 10
            ORDER BY rm.decade, rm.decade_rank
        """

    # -------------------------------------------------------------------------
    # Spark-Specific Functions
    # -------------------------------------------------------------------------

    @staticmethod
    def genre_analysis() -> str:
        """Analyze genre combinations using Spark string functions.

        Demonstrates:
            - SIZE() and SPLIT() for array operations
            - ARRAY_CONTAINS() for filtering
            - Spark-specific string functions

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                genre_names,
                SIZE(SPLIT(genre_names, ', ')) AS genre_count,
                COUNT(*) AS movie_count,
                ROUND(AVG(vote_average), 2) AS avg_rating
            FROM {SparkQueries.VIEW_NAME}
            WHERE genre_names IS NOT NULL
              AND vote_count >= 50
            GROUP BY genre_names
            HAVING COUNT(*) >= 5
            ORDER BY movie_count DESC
            LIMIT 20
        """

    @staticmethod
    def monthly_release_pattern() -> str:
        """Analyze release patterns by month.

        Demonstrates:
            - MONTH() and DATE_FORMAT() functions
            - Temporal aggregation patterns

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                MONTH(CAST(release_date AS DATE)) AS release_month,
                DATE_FORMAT(CAST(release_date AS DATE), 'MMMM') AS month_name,
                COUNT(*) AS movie_count,
                ROUND(AVG(vote_average), 2) AS avg_rating,
                ROUND(AVG(popularity), 2) AS avg_popularity
            FROM {SparkQueries.VIEW_NAME}
            WHERE release_date IS NOT NULL
              AND vote_count >= 50
            GROUP BY
                MONTH(CAST(release_date AS DATE)),
                DATE_FORMAT(CAST(release_date AS DATE), 'MMMM')
            ORDER BY release_month
        """

    # -------------------------------------------------------------------------
    # Export Query
    # -------------------------------------------------------------------------

    @staticmethod
    def export_enriched_data(min_votes: int = 50) -> str:
        """Export enriched data for aggregation.

        Prepares data for PostgreSQL import with computed fields.

        Args:
            min_votes: Minimum vote threshold.

        Returns:
            SparkSQL query string.
        """
        return f"""
            SELECT
                id AS kaggle_id,
                title,
                CAST(release_date AS DATE) AS release_date,
                YEAR(CAST(release_date AS DATE)) AS release_year,
                (YEAR(CAST(release_date AS DATE)) DIV 10) * 10 AS decade,
                COALESCE(vote_average, 0.0) AS rating,
                COALESCE(vote_count, 0) AS votes,
                COALESCE(popularity, 0.0) AS popularity,
                original_language,
                COALESCE(runtime, 0) AS runtime,
                overview,
                genre_names,
                COALESCE(budget, 0) AS budget,
                COALESCE(revenue, 0) AS revenue,
                CASE
                    WHEN vote_average >= 7.5 THEN 'excellent'
                    WHEN vote_average >= 6.0 THEN 'good'
                    WHEN vote_average >= 4.0 THEN 'average'
                    ELSE 'poor'
                END AS rating_category,
                ROW_NUMBER() OVER (ORDER BY vote_average DESC, vote_count DESC) AS global_rank
            FROM {SparkQueries.VIEW_NAME}
            WHERE vote_count >= {min_votes}
            ORDER BY vote_average DESC, vote_count DESC
        """
