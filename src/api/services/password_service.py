"""Password hashing and verification service.

Uses bcrypt directly for secure password storage.
"""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt.

    Args:
        password: Plain-text password.

    Returns:
        Bcrypt hash string.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: Plain-text password to check.
        hashed_password: Stored bcrypt hash.

    Returns:
        True if password matches hash.
    """
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
