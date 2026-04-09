from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=".env")

    DATABASE_URL: str = "sqlite+aiosqlite:///./talentflow.db"
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"
    DEBUG: bool = False
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"


settings = Settings()