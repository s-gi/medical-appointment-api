from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Security
    secret_key: str = "change-me-in-production-use-long-random-string"
    encryption_key: str = "change-me-32-byte-key-for-prod!"
    algorithm: str = "HS256"
    
    # JWT
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./medical_appointments.db"
    
    # Rate Limiting
    rate_limit_per_minute: int = 60
    
    # CORS
    allowed_origins: str = "http://localhost:3000"
    
    # Admin
    admin_email: str = "admin@clinic.com"
    admin_password: str = "ChangeThisPassword123!"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
