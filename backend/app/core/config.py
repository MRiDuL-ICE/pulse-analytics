from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Postgres
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432

    # Read replica (optional)
    postgres_replica_host: str | None = None
    postgres_replica_port: int = 5432

    postgres_test_db: str
    postgres_test_host: str
    postgres_test_port: int

    # Redis
    redis_url: str = "redis://localhost:6379"

    # App
    secret_key: str
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def replica_available(self) -> bool:
        return self.postgres_replica_host is not None

    @property
    def replica_test_available(self) -> bool:
        return self.postgres_test_host is not None


settings = Settings()