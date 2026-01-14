"""ProductionCompany model for film studios.

Stores studio information like Blumhouse, A24, etc.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class ProductionCompany(Base):
    """Film production company/studio.

    Attributes:
        id: Primary key.
        tmdb_company_id: TMDB company identifier.
        name: Company name.
        origin_country: ISO country code.
    """

    __tablename__ = "production_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_company_id: Mapped[int | None] = mapped_column(
        Integer,
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    origin_country: Mapped[str | None] = mapped_column(String(10))

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<ProductionCompany(id={self.id}, name='{self.name}')>"
