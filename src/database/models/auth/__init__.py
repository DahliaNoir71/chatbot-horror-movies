"""Authentication models package."""

from src.database.models.auth.admin_user import AdminUser
from src.database.models.auth.chatbot_user import ChatbotUser

__all__ = ["AdminUser", "ChatbotUser"]
