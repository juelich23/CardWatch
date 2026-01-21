from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

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

    # Add prepared_statement_cache_size=0 to URL for pgbouncer compatibility
    # This is more reliable than connect_args for asyncpg
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}prepared_statement_cache_size=0"

# Build engine kwargs based on database type
engine_kwargs = {
    "echo": settings.debug,
    "future": True,
}

if is_postgres:
    # PostgreSQL-specific settings for Supabase Transaction Pooler
    # Disable prepared statements for pgbouncer transaction mode compatibility
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 5,          # Base number of connections to keep
        "max_overflow": 5,       # Allow up to 5 additional connections under load
        "pool_recycle": 300,     # Recycle connections after 5 minutes
        "pool_timeout": 30,      # Wait up to 30 seconds for a connection
        "connect_args": {
            "statement_cache_size": 0,  # Disable prepared statements for pgbouncer
            "prepared_statement_cache_size": 0,
        },
    })

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
