import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ENVIRONMENT: str = "development"  # "development" or "production"

    ADMIN_API_KEY: str
    GRAPHHOPPER_API_KEY: Optional[str] = None
    GEOAPIFY_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    TOM_TOM_API_KEY: Optional[str] = None
    ROUTING_PROVIDER: str = "tomtom"  # "geoapify", "graphhopper", or "tomtom"

    # Redis / RQ
    REDIS_URL: str = "redis://localhost:6379/0"
    OPTIMIZATION_QUEUE_NAME: str = "optimization_queue"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
