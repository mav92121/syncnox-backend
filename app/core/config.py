import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    ENVIRONMENT: str = "development"  # "development" or "production"

    ADMIN_API_KEY: str
    GRAPHHOPPER_API_KEY: Optional[str] = None
    NEXTBILLION_API_KEY: Optional[str] = None
    NEXTBILLION_BASE_URL: str = "https://api.nextbillion.io"
    OPTIMIZATION_ENGINE: str = "nextbillion"  # "nextbillion" or "ortools"
    GEOAPIFY_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    TOM_TOM_API_KEY: Optional[str] = None
    OSRM_BASE_URL: str = "https://routing.syncnox.com"
    ROUTING_PROVIDER: str = "graphhopper"  # "osrm", "tomtom", "geoapify", or "graphhopper"

    # Redis / RQ
    REDIS_URL: str = "redis://localhost:6379/0"
    OPTIMIZATION_QUEUE_NAME: str = "optimization_queue"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

class LazySettings:
    _instance: Optional[Settings] = None

    def _load(self) -> Settings:
        # Always recreate if needed (fresh env)
        self._instance = Settings()
        return self._instance

    def __getattr__(self, name):
        settings = self._load()
        return getattr(settings, name)


# 👇 This keeps your existing usage intact
settings = LazySettings()
