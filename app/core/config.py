import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    COOKIE_NAME: str = "access_token"
    ENVIRONMENT: str = "development"  # "development" or "production"

    @property
    def cookie_secure(self):
        return self.ENVIRONMENT == "production"

    @property
    def cookie_samesite(self):
        return "None" if self.ENVIRONMENT == "production" else "Lax"

    @property
    def cookie_domain(self):
        return ".syncnox.com" if self.ENVIRONMENT == "production" else None

    @property
    def cookie_max_age(self):
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    ADMIN_API_KEY: str
    GRAPHHOPPER_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
