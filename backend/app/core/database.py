from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# The engine manages the actual connection pool to Postgres
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,   # logs every SQL statement when DEBUG=true
    pool_size=10,          # max persistent connections in the pool
    max_overflow=20,       # extra connections allowed under heavy load
)

# A factory that produces AsyncSession objects
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # don't expire objects after commit so we can still read them
)


# All ORM models will inherit from this base class
class Base(DeclarativeBase):
    pass