"""Chatbot user repository with authentication-specific queries."""

from sqlalchemy.orm import Session

from src.database.models.auth.chatbot_user import ChatbotUser
from src.database.repositories.base import BaseRepository


class ChatbotUserRepository(BaseRepository[ChatbotUser]):
    """Repository for ChatbotUser entity operations.

    Provides methods for querying chatbot users by username and email.
    """

    model = ChatbotUser

    def __init__(self, session: Session) -> None:
        """Initialize chatbot user repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_username(self, username: str) -> ChatbotUser | None:
        """Retrieve chatbot user by username.

        Args:
            username: Username to look up.

        Returns:
            ChatbotUser instance or None.
        """
        return self.get_by_field("username", username)

    def get_by_email(self, email: str) -> ChatbotUser | None:
        """Retrieve chatbot user by email.

        Args:
            email: Email to look up.

        Returns:
            ChatbotUser instance or None.
        """
        return self.get_by_field("email", email)

    def username_exists(self, username: str) -> bool:
        """Check if a username is already taken.

        Args:
            username: Username to check.

        Returns:
            True if username exists.
        """
        return self.get_by_username(username) is not None

    def email_exists(self, email: str) -> bool:
        """Check if an email is already registered.

        Args:
            email: Email to check.

        Returns:
            True if email exists.
        """
        return self.get_by_email(email) is not None
