"""Pydantic schemas for API request/response validation.

Defines data transfer objects for films, authentication, and search.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# HEALTH
# =============================================================================


class LLMComponentHealth(BaseModel):
    """LLM service health status."""

    loaded: bool = False
    memory_mb: int | None = None


class DatabaseComponentHealth(BaseModel):
    """Database connection health status."""

    connected: bool = False
    pool_available: int | None = None


class EmbeddingsComponentHealth(BaseModel):
    """Embeddings service health status."""

    model_loaded: bool = False


class HealthComponents(BaseModel):
    """Health status of all system components."""

    llm: LLMComponentHealth = Field(default_factory=LLMComponentHealth)
    database: DatabaseComponentHealth = Field(default_factory=DatabaseComponentHealth)
    embeddings: EmbeddingsComponentHealth = Field(default_factory=EmbeddingsComponentHealth)


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(examples=["healthy"])
    version: str = Field(examples=["1.0.0"])
    components: HealthComponents = Field(default_factory=HealthComponents)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# AUTHENTICATION
# =============================================================================


class TokenRequest(BaseModel):
    """Token request schema (login credentials)."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)


class TokenResponse(BaseModel):
    """JWT token response schema."""

    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = Field(description="Token lifetime in seconds")


# =============================================================================
# PAGINATION
# =============================================================================


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, le=1000)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        """Calculate SQL offset from page number."""
        return (self.page - 1) * self.size


class PaginatedMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int
    size: int
    total: int
    pages: int

    @classmethod
    def from_params(
        cls,
        params: PaginationParams,
        total: int,
    ) -> "PaginatedMeta":
        """Build meta from pagination params and total count."""
        pages = (total + params.size - 1) // params.size if total > 0 else 0
        return cls(
            page=params.page,
            size=params.size,
            total=total,
            pages=pages,
        )


# =============================================================================
# FILM SCHEMAS
# =============================================================================


class FilmBase(BaseModel):
    """Base film schema with common fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int
    title: str
    release_date: date | None = None
    vote_average: float | None = None
    popularity: float | None = None
    poster_path: str | None = None


class FilmDetail(FilmBase):
    """Detailed film schema with all fields."""

    imdb_id: str | None = None
    original_title: str | None = None
    overview: str | None = None
    runtime: int | None = None
    budget: int | None = None
    revenue: int | None = None
    vote_count: int | None = None
    tagline: str | None = None
    status: str | None = None
    original_language: str | None = None


class FilmListResponse(BaseModel):
    """Paginated film list response."""

    data: list[FilmBase]
    meta: PaginatedMeta


# =============================================================================
# SEARCH SCHEMAS
# =============================================================================


class SearchRequest(BaseModel):
    """Semantic search request schema."""

    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class SearchResultItem(BaseModel):
    """Single search result with similarity score."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int
    title: str
    overview: str | None = None
    release_date: date | None = None
    score: float = Field(description="Similarity score (0-1)")


class SearchResponse(BaseModel):
    """Semantic search response schema."""

    query: str
    results: list[SearchResultItem]
    count: int


# =============================================================================
# CHAT SCHEMAS
# =============================================================================


class ChatRequest(BaseModel):
    """Chat endpoint request schema."""

    message: str = Field(min_length=1, max_length=2000, description="User message")
    session_id: str | None = Field(
        default=None,
        description="Session UUID for multi-turn. Omit for new session.",
    )


class ChatResponse(BaseModel):
    """Synchronous chat response schema."""

    response: str = Field(description="Bot response text")
    intent: str = Field(description="Classified intent label")
    confidence: float = Field(description="Classifier confidence (0.0-1.0)")
    session_id: str = Field(description="Session UUID for subsequent requests")


class StreamChunk(BaseModel):
    """SSE stream chunk schema.

    Serialized as JSON in each SSE data field.
    type='chunk' for text fragments, type='done' for final metadata.
    """

    type: str = Field(description="Event type: 'chunk' or 'done'")
    content: str | None = Field(default=None, description="Text chunk (for type='chunk')")
    intent: str | None = Field(default=None, description="Intent (for type='done')")
    confidence: float | None = Field(default=None, description="Confidence (for type='done')")
    session_id: str | None = Field(default=None, description="Session ID (for type='done')")
