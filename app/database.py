import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set.\n"
        "Make sure it exists in your .env locally and in Render environment variables."
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Test connections before using
    pool_size=10,            # Base connection pool size
    max_overflow=20,         # Max connections beyond pool_size
    pool_timeout=30,         # Timeout for getting connection (seconds)
    pool_recycle=3600,       # Recycle connections after 1 hour
    echo=False,              # Set to True for debugging SQL logs
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# Import and use logger
from app.core.logging_config import logger
logger.info("Database connected successfully")

from sqlalchemy import Column, DateTime, func

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
