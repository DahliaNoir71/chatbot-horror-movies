"""SpokenLanguage model for film languages.

Stores ISO 639-1 language codes and names.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base


class SpokenLanguage(Base):
    """Language spoken in films.

    Attributes:
        id: Primary key.
        iso_639_1: ISO language code (e.g., 'en', 'fr').
        name: Language name in English.
    """

    __tablename__ = "spoken_languages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iso_639_1: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<SpokenLanguage(iso='{self.iso_639_1}', name='{self.name}')>"
