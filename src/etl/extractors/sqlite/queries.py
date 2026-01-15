"""IMDB SQL queries for C2 competency validation.

Contains native SQL queries demonstrating:
- JOIN operations (titles + ratings)
- WHERE clauses with LIKE for genre filtering
- Aggregate functions (AVG, COUNT, MIN, MAX)
- ORDER BY and LIMIT clauses
- BETWEEN for date ranges
- Subqueries for complex filtering

Note:
    imdb-sqlite schema uses 'crew' table from title.principals.tsv
    with columns: title_id, ordering, name_id, category, job, characters
    Directors are identified by category = 'director'.
"""


class IMDBQueries:
    """Native SQL queries for IMDB SQLite database.

    All queries are written in raw SQL to validate
    C2 competency (SQL query writing).

    Table structure (imdb-sqlite):
        - titles: title_id, type, primary_title, original_title,
                  genres, premiered, runtime_minutes
        - ratings: title_id, rating, votes
        - crew: title_id, ordering, name_id, category, job, characters
        - people: name_id, name, born, died
    """

    # -------------------------------------------------------------------------
    # Core Horror Movie Queries
    # -------------------------------------------------------------------------

    @staticmethod
    def horror_movies_with_ratings(
        min_votes: int = 1000,
        min_rating: float = 0.0,
    ) -> str:
        """Get horror movies with ratings via JOIN.

        Demonstrates:
            - INNER JOIN between titles and ratings
            - WHERE with LIKE for genre filtering
            - Multiple filter conditions

        Args:
            min_votes: Minimum vote threshold.
            min_rating: Minimum rating threshold.

        Returns:
            SQL query string.
        """
        return f"""
            SELECT
                t.title_id AS imdb_id,
                t.primary_title AS title,
                t.original_title,
                t.premiered AS year,
                t.runtime_minutes AS runtime,
                t.genres,
                r.rating,
                r.votes
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND r.votes >= {min_votes}
                AND r.rating >= {min_rating}
            ORDER BY r.rating DESC, r.votes DESC
        """

    @staticmethod
    def top_rated_horror(
        min_votes: int = 1000,
        limit: int = 100,
    ) -> str:
        """Get top rated horror movies.

        Demonstrates:
            - ORDER BY with multiple columns
            - LIMIT clause
            - Descending sort

        Args:
            min_votes: Minimum vote threshold.
            limit: Maximum results.

        Returns:
            SQL query string.
        """
        return f"""
            SELECT
                t.title_id AS imdb_id,
                t.primary_title AS title,
                t.original_title,
                t.premiered AS year,
                t.runtime_minutes AS runtime,
                t.genres,
                r.rating,
                r.votes
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND r.votes >= {min_votes}
            ORDER BY r.rating DESC, r.votes DESC
            LIMIT {limit}
        """

    @staticmethod
    def horror_by_decade(
        decade: int,
        min_votes: int = 500,
    ) -> str:
        """Get horror movies from a specific decade.

        Demonstrates:
            - BETWEEN clause for date range
            - Calculated year boundaries

        Args:
            decade: Start year of decade (e.g., 1980).
            min_votes: Minimum vote threshold.

        Returns:
            SQL query string.
        """
        end_year = decade + 9
        return f"""
            SELECT
                t.title_id AS imdb_id,
                t.primary_title AS title,
                t.original_title,
                t.premiered AS year,
                t.runtime_minutes AS runtime,
                t.genres,
                r.rating,
                r.votes
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND t.premiered BETWEEN {decade} AND {end_year}
                AND r.votes >= {min_votes}
            ORDER BY r.rating DESC
        """

    # -------------------------------------------------------------------------
    # Aggregate Queries
    # -------------------------------------------------------------------------

    @staticmethod
    def horror_statistics(min_votes: int = 1000) -> str:
        """Get aggregate statistics for horror movies.

        Demonstrates:
            - COUNT, AVG, MIN, MAX aggregate functions
            - ROUND for decimal precision
            - Single-row result

        Args:
            min_votes: Minimum vote threshold.

        Returns:
            SQL query string.
        """
        return f"""
            SELECT
                COUNT(*) AS total_movies,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                MIN(r.rating) AS min_rating,
                MAX(r.rating) AS max_rating,
                ROUND(AVG(r.votes), 0) AS avg_votes,
                MIN(t.premiered) AS earliest_year,
                MAX(t.premiered) AS latest_year,
                ROUND(AVG(t.runtime_minutes), 0) AS avg_runtime
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND r.votes >= {min_votes}
        """

    @staticmethod
    def horror_count_by_decade() -> str:
        """Count horror movies by decade.

        Demonstrates:
            - GROUP BY with calculated expression
            - Integer division for decade grouping
            - Ordering by grouped column

        Returns:
            SQL query string.
        """
        return """
            SELECT
                (t.premiered / 10) * 10 AS decade,
                COUNT(*) AS movie_count,
                ROUND(AVG(r.rating), 2) AS avg_rating
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND t.premiered IS NOT NULL
                AND r.votes >= 500
            GROUP BY (t.premiered / 10) * 10
            ORDER BY decade
        """

    @staticmethod
    def horror_count_by_genre_combination() -> str:
        """Count horror movies by genre combination.

        Demonstrates:
            - GROUP BY on text field
            - HAVING clause for filtering groups
            - Ordering by aggregate result

        Returns:
            SQL query string.
        """
        return """
            SELECT
                t.genres,
                COUNT(*) AS movie_count,
                ROUND(AVG(r.rating), 2) AS avg_rating
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND r.votes >= 1000
            GROUP BY t.genres
            HAVING COUNT(*) >= 10
            ORDER BY movie_count DESC
        """

    # -------------------------------------------------------------------------
    # Subquery Examples
    # -------------------------------------------------------------------------

    @staticmethod
    def horror_above_average_rating(min_votes: int = 1000) -> str:
        """Get horror movies above average rating.

        Demonstrates:
            - Subquery in WHERE clause
            - Comparison with aggregate result

        Args:
            min_votes: Minimum vote threshold.

        Returns:
            SQL query string.
        """
        return f"""
            SELECT
                t.title_id AS imdb_id,
                t.primary_title AS title,
                t.premiered AS year,
                r.rating,
                r.votes
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND r.votes >= {min_votes}
                AND r.rating > (
                    SELECT AVG(r2.rating)
                    FROM titles t2
                    INNER JOIN ratings r2 ON r2.title_id = t2.title_id
                    WHERE t2.type = 'movie'
                        AND t2.genres LIKE '%Horror%'
                        AND r2.votes >= {min_votes}
                )
            ORDER BY r.rating DESC
        """

    @staticmethod
    def top_directors_by_horror_count(min_movies: int = 3) -> str:
        """Get directors with most horror movies.

        Demonstrates:
            - Multiple JOINs (titles, ratings, crew, people)
            - Filtering by category
            - GROUP BY with HAVING

        Args:
            min_movies: Minimum movies directed.

        Returns:
            SQL query string.
        """
        return f"""
            SELECT
                p.name AS director_name,
                COUNT(*) AS horror_count,
                ROUND(AVG(r.rating), 2) AS avg_rating
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            INNER JOIN crew c ON c.title_id = t.title_id
            INNER JOIN people p ON p.name_id = c.name_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND c.category = 'director'
                AND r.votes >= 1000
            GROUP BY p.name_id, p.name
            HAVING COUNT(*) >= {min_movies}
            ORDER BY horror_count DESC, avg_rating DESC
            LIMIT 50
        """

    # -------------------------------------------------------------------------
    # IMDB ID Matching Query
    # -------------------------------------------------------------------------

    @staticmethod
    def horror_movies_for_enrichment(imdb_ids: list[str]) -> str:
        """Get specific horror movies by IMDB IDs for enrichment.

        Demonstrates:
            - IN clause with list of values

        Args:
            imdb_ids: List of IMDB tconst values.

        Returns:
            SQL query string.
        """
        ids_str = ", ".join(f"'{id}'" for id in imdb_ids)
        return f"""
            SELECT
                t.title_id AS imdb_id,
                t.primary_title AS title,
                t.runtime_minutes AS runtime,
                r.rating,
                r.votes
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.title_id IN ({ids_str})
        """

    @staticmethod
    def all_horror_imdb_ids(min_votes: int = 100) -> str:
        """Get all IMDB IDs for horror movies.

        Used for matching with existing films.

        Args:
            min_votes: Minimum vote threshold.

        Returns:
            SQL query string.
        """
        return f"""
            SELECT DISTINCT t.title_id AS imdb_id
            FROM titles t
            INNER JOIN ratings r ON r.title_id = t.title_id
            WHERE t.type = 'movie'
                AND t.genres LIKE '%Horror%'
                AND r.votes >= {min_votes}
        """
