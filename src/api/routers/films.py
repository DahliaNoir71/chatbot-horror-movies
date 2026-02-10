"""Film endpoints for REST API.

Provides endpoints for listing, retrieving, and searching films
with JWT authentication and rate limiting.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.rate_limit import check_rate_limit
from src.api.schemas import (
    FilmBase,
    FilmDetail,
    FilmListResponse,
    PaginatedMeta,
    PaginationParams,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from src.database.models.tmdb import Film

router = APIRouter(
    prefix="/films",
    tags=["Films"],
    dependencies=[Depends(check_rate_limit)],
)


# =============================================================================
# DEPENDENCIES
# =============================================================================


def get_pagination(
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginationParams:
    """Parse and validate pagination parameters.

    Args:
        page: Page number (1-indexed).
        size: Items per page.

    Returns:
        Validated pagination parameters.
    """
    return PaginationParams(page=page, size=size)


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "",
    response_model=FilmListResponse,
    summary="List films",
    description="Get paginated list of films sorted by popularity.",
)
def list_films(
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> FilmListResponse:
    """Get paginated film list.

    Args:
        _user: Authenticated user (JWT validated).
        db: Database session.
        pagination: Pagination parameters.

    Returns:
        Paginated list of films with metadata.
    """
    total = _count_films(db)
    films = _fetch_films_page(db, pagination)
    return FilmListResponse(
        data=[FilmBase.model_validate(f) for f in films],
        meta=PaginatedMeta.from_params(pagination, total),
    )


@router.get(
    "/{film_id}",
    response_model=FilmDetail,
    summary="Get film details",
    description="Retrieve detailed information for a specific film.",
)
def get_film(
    film_id: int,
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> FilmDetail:
    """Get film by ID.

    Args:
        film_id: Film primary key.
        _user: Authenticated user (JWT validated).
        db: Database session.

    Returns:
        Detailed film information.

    Raises:
        HTTPException: 404 if film not found.
    """
    film = db.get(Film, film_id)
    if not film:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Film with id {film_id} not found",
        )
    return FilmDetail.model_validate(film)


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search",
    description="Search films using vector similarity on embeddings.",
)
def search_films(
    request: SearchRequest,
    _user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> SearchResponse:
    """Search films by semantic similarity.

    Args:
        request: Search query and parameters.
        _user: Authenticated user (JWT validated).
        db: Database session.

    Returns:
        Search results ranked by similarity score.
    """
    results = _execute_vector_search(db, request.query, request.limit)
    return SearchResponse(
        query=request.query,
        results=results,
        count=len(results),
    )


# =============================================================================
# PRIVATE HELPERS
# =============================================================================


def _count_films(db: Session) -> int:
    """Count total films in database.

    Args:
        db: Database session.

    Returns:
        Total film count.
    """
    result = db.execute(select(func.count(Film.id)))
    return result.scalar() or 0


def _fetch_films_page(
    db: Session,
    pagination: PaginationParams,
) -> list[Film]:
    """Fetch paginated films ordered by popularity.

    Args:
        db: Database session.
        pagination: Pagination parameters.

    Returns:
        List of films for current page.
    """
    stmt = (
        select(Film)
        .order_by(Film.popularity.desc())
        .offset(pagination.offset)
        .limit(pagination.size)
    )
    return list(db.scalars(stmt).all())


def _execute_vector_search(
    db: Session,
    query: str,
    limit: int,
) -> list[SearchResultItem]:
    """Execute vector similarity search.

    Uses pgvector cosine distance for semantic search.

    Args:
        db: Database session.
        query: Search query text.
        limit: Maximum results.

    Returns:
        List of search results with similarity scores.
    """
    # Import here to avoid circular dependency
    from src.services.embedding.embedding_service import get_embedding_service

    embedding_service = get_embedding_service()
    query_embedding = embedding_service.encode(query)

    # pgvector cosine distance: 1 - cosine_similarity
    sql = text("""
               SELECT id,
                      tmdb_id,
                      title,
                      overview,
                      release_date,
                      1 - (embedding <=> :embedding::vector) AS score
               FROM films
               WHERE embedding IS NOT NULL
               ORDER BY embedding <=> :embedding::vector
               LIMIT :limit
               """)

    result = db.execute(
        sql,
        {"embedding": str(query_embedding), "limit": limit},
    )

    return [
        SearchResultItem(
            id=row.id,
            tmdb_id=row.tmdb_id,
            title=row.title,
            overview=row.overview,
            release_date=row.release_date,
            score=round(float(row.score), 4),
        )
        for row in result
    ]
