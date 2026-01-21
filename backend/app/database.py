import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Determine if we're using PostgreSQL or SQLite
# Note: Supabase/some providers use postgres:// while SQLAlchemy prefers postgresql://
is_postgres = settings.database_url.startswith("postgresql") or settings.database_url.startswith("postgres://")

# Transform the database URL to use the correct async driver
database_url = settings.database_url
if is_postgres:
    # Convert postgres:// or postgresql:// to postgresql+asyncpg://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Build engine kwargs based on database type
engine_kwargs = {
    "echo": settings.debug,
}

if is_postgres:
    # PostgreSQL-specific settings for Supabase/pgbouncer Transaction Pooler
    # Use NullPool - let pgbouncer handle connection pooling
    # Disable prepared statements (required for pgbouncer transaction mode)
    engine_kwargs.update({
        "poolclass": NullPool,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    })

# Log configuration for debugging (v2 - 2026-01-21)
print(f"[DATABASE CONFIG v2] is_postgres={is_postgres}, using NullPool={is_postgres}, statement_cache_size=0")
logger.info(f"Database config v2: is_postgres={is_postgres}, poolclass={'NullPool' if is_postgres else 'default'}")

engine = create_async_engine(database_url, **engine_kwargs)

# Async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
