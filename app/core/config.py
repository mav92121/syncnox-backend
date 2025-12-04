import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ENVIRONMENT: str = "development"  # "development" or "production"

    ADMIN_API_KEY: str
    GRAPHHOPPER_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
