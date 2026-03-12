from arq.connections import RedisSettings as ArqRedisSettings
from pydantic import BaseModel, SecretStr
from pydantic.networks import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """Stores all environment variables related to connecting to the database."""

    USER: str = "postgres"
    PASS: SecretStr
    HOST: str = "localhost"
    PORT: int = 5432
    NAME: str = "saga"

    @property
    def DATABASE_URL(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.USER,
                password=self.PASS.get_secret_value(),
                host=self.HOST,
                port=self.PORT,
                path=self.NAME,
            )
        )


class RedisSettings(BaseModel):
    """Redis connection configuration."""

    R_HOST: str = "localhost"
    R_PORT: int = 6379

    @property
    def arq_settings(self) -> ArqRedisSettings:
        """
        Forms a settings object for the ARQ worker.
        ARQ uses its own RedisSettings format, which differs from redis-py.
        """
        return ArqRedisSettings(
            host=self.R_HOST,
            port=self.R_PORT,
        )


class AuthSettings(BaseModel):
    """JWT token configuration."""

    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


class Settings(BaseSettings):
    """
    The main class aggregator, which is the sole source of configuration for the entire application.
    Pydantic automatically loads and validates settings at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    debug_mode: bool = False

    db: DatabaseSettings
    redis: RedisSettings
    auth: AuthSettings


settings = Settings()  # type: ignore[call-arg]
