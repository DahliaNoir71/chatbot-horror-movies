"""User model for authentication.

Stores user credentials with bcrypt-hashed passwords.
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User account for authentication.

    Attributes:
        id: Primary key.
        username: Unique username (3-50 chars).
        email: Unique email address.
        password_hash: Bcrypt-hashed password.
        is_active: Whether the account is active.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<User(id={self.id}, username='{self.username}')>"
