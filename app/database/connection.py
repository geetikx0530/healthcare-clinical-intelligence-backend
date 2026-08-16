from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.core.config import settings

# Create SQLAlchemy 2.x Engine
# pool_pre_ping=True checks connection validity before using pooled connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Create SessionLocal factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class for SQLAlchemy ORM models (used in Phase 4)
class Base(DeclarativeBase):
    pass


# FastAPI dependency to yield database session per request
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Safe database health / connectivity check
def check_db_connection() -> dict:
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();")).scalar()
            return {
                "connected": True,
                "version": result,
                "database_url": settings.DATABASE_URL.split("@")[-1]  # Hide credentials
            }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }
