from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CIOS - Clinical Intelligence Operating System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://cios_user:cios_secret@localhost:5432/cios_db"
    # ICU Database (optional) — if set, CIOS can connect to ICU monitoring DB
    ICU_DATABASE_URL: str = "postgresql://icu_user:icu_password@localhost:5433/icu_monitoring"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_CONFIDENCE_THRESHOLD: float = 0.75
    AI_HIGH_RISK_THRESHOLD: float = 0.70
    AI_MEDIUM_RISK_THRESHOLD: float = 0.40

    # Reports
    REPORTS_DIR: str = "./reports"
    MAX_REPORT_AGE_DAYS: int = 30

    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:80"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
