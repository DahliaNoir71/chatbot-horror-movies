"""FilmCompany association table.

Many-to-many relationship between Film and ProductionCompany.
"""

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class FilmCompany(Base):
    """Association table for Film-ProductionCompany relationship.

    Attributes:
        film_id: Foreign key to films.
        company_id: Foreign key to production_companies.
    """

    __tablename__ = "film_companies"

    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("production_companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
