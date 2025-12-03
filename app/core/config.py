import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # JWT Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Cookie Configuration
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = True  # Set to True in production (HTTPS only)
    COOKIE_SAMESITE: str = "None"  # CSRF protection
    COOKIE_HTTPONLY: bool = True  # Prevent JavaScript access
    ENVIRONMENT: str = "development"  # development or production
    
    @property
    def cookie_max_age(self) -> int:
        """Cookie expiration in seconds, matching token expiration."""
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    # Admin API Key
    ADMIN_API_KEY: str
    
    # Optimization
    GRAPHHOPPER_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

