from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# Shared SQLAlchemy engine for the whole application process.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


# Session factory used by request handlers and websocket handlers.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Description: Class `Base` encapsulates related data and behavior for this module.
class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""

    pass


# Description: Function `get_db` implementation.
# Inputs: None
# Output: AsyncSession
# Exceptions: Propagates exceptions raised by internal operations.
async def get_db() -> AsyncSession:
    """Yield a transaction-scoped async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
