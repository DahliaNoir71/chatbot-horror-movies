"""API configuration settings.

FastAPI, security (JWT), and CORS settings for E3.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    """FastAPI configuration.

    Attributes:
        host: API host address.
        port: API port.
        reload: Enable auto-reload in development.
        workers: Number of worker processes.
        public_url: Public URL for the API.
    """

    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    reload: bool = Field(default=True, alias="API_RELOAD")
    workers: int = Field(default=4, alias="API_WORKERS")
    public_url: str = Field(default="http://localhost:8000", alias="API_PUBLIC_URL")
    title: str = Field(default="HorrorBot API", alias="API_TITLE")
    version: str = Field(default="1.0.0", alias="API_VERSION")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class SecuritySettings(BaseSettings):
    """JWT and rate limiting configuration.

    Attributes:
        jwt_secret_key: Secret key for JWT signing.
        jwt_algorithm: JWT algorithm (HS256, RS256).
        jwt_expire_minutes: Token expiration time.
        rate_limit_per_minute: Max requests per minute.
        rate_limit_per_hour: Max requests per hour.
    """

    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, alias="JWT_EXPIRE_MINUTES")
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")

    # Demo authentication (format: "user1:pass1,user2:pass2")
    demo_users_raw: str = Field(default="", alias="AUTH_DEMO_USERS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if JWT secret is configured and secure."""
        return bool(self.jwt_secret_key and len(self.jwt_secret_key) >= 32)

    @property
    def demo_users(self) -> dict[str, str]:
        """Parse demo users from 'user:pass,user:pass' format."""
        if not self.demo_users_raw:
            return {}
        users = {}
        for pair in self.demo_users_raw.split(","):
            if ":" in pair:
                username, password = pair.strip().split(":", 1)
                users[username.strip()] = password.strip()
        return users


class CORSSettings(BaseSettings):
    """CORS configuration.

    Attributes:
        origins_raw: Comma-separated allowed origins.
    """

    origins_raw: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def origins(self) -> list[str]:
        """Parse origins from comma-separated string."""
        return [o.strip() for o in self.origins_raw.split(",") if o.strip()]
