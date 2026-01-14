"""RTScore model for Rotten Tomatoes data.

Stores critic and audience scores scraped from RT website.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class RTScore(Base):
    """Rotten Tomatoes scores for a film.

    Attributes:
        id: Primary key.
        film_id: Foreign key to films (1:1 relationship).
        tomatometer_score: Critic score (0-100).
        audience_score: Audience score (0-100).
        critics_consensus: Summary text from critics (for RAG).
    """

    __tablename__ = "rt_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Critic scores (Tomatometer)
    tomatometer_score: Mapped[int | None] = mapped_column(Integer)
    tomatometer_state: Mapped[str | None] = mapped_column(String(20))
    critics_count: Mapped[int] = mapped_column(Integer, default=0)
    critics_average_rating: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # Audience scores
    audience_score: Mapped[int | None] = mapped_column(Integer)
    audience_state: Mapped[str | None] = mapped_column(String(20))
    audience_count: Mapped[int] = mapped_column(Integer, default=0)
    audience_average_rating: Mapped[float | None] = mapped_column(Numeric(3, 2))

    # Critics consensus (valuable for RAG)
    critics_consensus: Mapped[str | None] = mapped_column(Text)

    # RT metadata
    rt_url: Mapped[str | None] = mapped_column(String(500))
    rt_rating: Mapped[str | None] = mapped_column(String(20))

    # ETL metadata
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("idx_rt_scores_tomatometer", "tomatometer_score"),)

    @property
    def is_certified_fresh(self) -> bool:
        """Check if film has Certified Fresh status."""
        return self.tomatometer_state == "certified_fresh"

    @property
    def is_fresh(self) -> bool:
        """Check if film is Fresh (>= 60% Tomatometer)."""
        if self.tomatometer_score is None:
            return False
        return self.tomatometer_score >= 60

    @property
    def is_rotten(self) -> bool:
        """Check if film is Rotten (< 60% Tomatometer)."""
        if self.tomatometer_score is None:
            return False
        return self.tomatometer_score < 60

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<RTScore(film_id={self.film_id}, "
            f"tomatometer={self.tomatometer_score}, "
            f"audience={self.audience_score})>"
        )
