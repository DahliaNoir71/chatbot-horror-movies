"""Film endpoints for REST API.

Provides endpoints for listing, retrieving, and searching films
with JWT authentication and rate limiting.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.database import get_db
from src.api.dependencies.auth import AdminUser
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
    summary="List films",
    description="Get paginated list of films sorted by popularity.",
)
def list_films(
    _user: AdminUser,
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
    summary="Get film details",
    description="Retrieve detailed information for a specific film.",
)
def get_film(
    film_id: int,
    _user: AdminUser,
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
    summary="Semantic search",
    description="Search films using vector similarity on embeddings.",
)
def search_films(
    request: SearchRequest,
    _user: AdminUser,
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
    """Execute vector similarity search against horrorbot_vectors.

    Retrieves documents from rag_documents (horrorbot_vectors) then
    fetches film metadata from films (horrorbot) via tmdb_id.

    Args:
        db: Database session for horrorbot (film metadata).
        query: Search query text.
        limit: Maximum results.

    Returns:
        List of search results with similarity scores.
    """
    from src.services.rag.retriever import get_document_retriever

    retriever = get_document_retriever()
    # Over-fetch to account for multiple rag_documents per film
    docs = retriever.retrieve(query, match_count=limit * 3, similarity_threshold=0.1)

    # Deduplicate by tmdb_id, keep best similarity per film
    best_score: dict[int, float] = {}
    for doc in docs:
        if doc.source_id not in best_score or doc.similarity > best_score[doc.source_id]:
            best_score[doc.source_id] = doc.similarity

    # Sort by score desc and take top-limit tmdb_ids
    ranked_ids = sorted(best_score, key=lambda tid: best_score[tid], reverse=True)[:limit]

    if not ranked_ids:
        return []

    films_map: dict[int, Film] = {
        f.tmdb_id: f for f in db.scalars(select(Film).where(Film.tmdb_id.in_(ranked_ids))).all()
    }

    return [
        SearchResultItem(
            id=film.id,
            tmdb_id=film.tmdb_id,
            title=film.title,
            overview=film.overview,
            release_date=film.release_date,
            score=round(best_score[tmdb_id], 4),
        )
        for tmdb_id in ranked_ids
        if (film := films_map.get(tmdb_id)) is not None
    ]
