"""Admin user repository with authentication-specific queries."""

from sqlalchemy.orm import Session

from src.database.models.auth.admin_user import AdminUser
from src.database.repositories.base import BaseRepository


class AdminUserRepository(BaseRepository[AdminUser]):
    """Repository for AdminUser entity operations.

    Provides methods for querying admin users by email.
    """

    model = AdminUser

    def __init__(self, session: Session) -> None:
        """Initialize admin user repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_email(self, email: str) -> AdminUser | None:
        """Retrieve admin user by email.

        Args:
            email: Email to look up.

        Returns:
            AdminUser instance or None.
        """
        return self.get_by_field("email", email)

    def email_exists(self, email: str) -> bool:
        """Check if an email is already registered.

        Args:
            email: Email to check.

        Returns:
            True if email exists.
        """
        return self.get_by_email(email) is not None
