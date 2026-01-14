"""Credit model for film crew and cast.

Stores directors, actors, writers, and producers
associated with a film.
"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class Credit(Base):
    """Film crew and cast member.

    Attributes:
        id: Primary key.
        film_id: Foreign key to films.
        tmdb_person_id: TMDB person identifier.
        person_name: Name of the person.
        role_type: One of 'director', 'actor', 'writer', 'producer'.
        character_name: Character name (for actors).
        department: Department (Acting, Directing, etc.).
        job: Specific job title.
        display_order: Order for cast listing.
        profile_path: TMDB profile image path.
    """

    __tablename__ = "credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("films.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tmdb_person_id: Mapped[int | None] = mapped_column(Integer)

    # Person info
    person_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Role info
    role_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    character_name: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(100))
    job: Mapped[str | None] = mapped_column(String(100))

    # Display order for cast
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Media
    profile_path: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        CheckConstraint(
            "role_type IN ('director', 'actor', 'writer', 'producer')",
            name="chk_role_type",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Credit(id={self.id}, person='{self.person_name}', role='{self.role_type}')>"
