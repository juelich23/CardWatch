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
# Using psycopg (psycopg3) instead of asyncpg for better pgbouncer compatibility
database_url = settings.database_url
if is_postgres:
    # Convert postgres:// or postgresql:// to postgresql+psycopg://
    # psycopg3 has native support for pgbouncer transaction mode
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "+psycopg")
    elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

# Build engine kwargs based on database type
engine_kwargs = {
    "echo": settings.debug,
}

if is_postgres:
    # PostgreSQL-specific settings for Supabase/pgbouncer Transaction Pooler
    # Use NullPool - let pgbouncer handle connection pooling
    # psycopg3 handles pgbouncer transaction mode natively without prepared statement issues
    engine_kwargs.update({
        "poolclass": NullPool,
        "connect_args": {
            # Disable prepared statements for pgbouncer compatibility
            "prepare_threshold": None,
        },
    })

# Log configuration for debugging (v3 - using psycopg3)
print(f"[DATABASE CONFIG v3] is_postgres={is_postgres}, using psycopg driver, NullPool={is_postgres}")
logger.info(f"Database config v3: is_postgres={is_postgres}, driver=psycopg, poolclass={'NullPool' if is_postgres else 'default'}")

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
        # Note: async with already handles session cleanup, no explicit close needed


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
