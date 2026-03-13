"""Admin user model for authentication.

Stores admin credentials with bcrypt-hashed passwords.
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin


class AdminUser(Base, TimestampMixin):
    """Admin account for authentication.

    Attributes:
        id: Primary key.
        email: Unique email address (used as login identifier).
        password_hash: Bcrypt-hashed password.
        is_active: Whether the account is active.
    """

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
        return f"<AdminUser(id={self.id}, email='{self.email}')>"
