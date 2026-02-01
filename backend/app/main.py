import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from strawberry.fastapi import GraphQLRouter
from app.database import init_db, get_db, async_session_maker
from app.config import get_settings
from app.graphql.schema import schema
from app.api.auth import router as auth_router
from app.api.saved_searches import router as saved_searches_router
from app.api.ai_search import router as ai_search_router
from app.api.scheduler import router as scheduler_router
from app.services.auth import AuthService
from app.services.scheduler import scheduler
from app.services.scraper_jobs import SCRAPER_JOBS
from sqlalchemy import text

settings = get_settings()


async def run_migrations():
    """Run pending database migrations on startup.

    Note: Migrations are non-blocking - failures are logged but don't prevent startup.
    This prevents connection pool timeouts from blocking app startup.
    """
    from app.database import database_url
    is_postgres = "postgresql" in database_url or "postgres" in database_url
    print(f"Migration: Starting (is_postgres={is_postgres})")

    try:
        async with async_session_maker() as session:
            if is_postgres:
                # Check which indexes already exist to avoid unnecessary work
                try:
                    result = await session.execute(text(
                        "SELECT indexname FROM pg_indexes WHERE tablename = 'auction_items'"
                    ))
                    existing_indexes = {row[0] for row in result.fetchall()}
                    print(f"Migration: Existing indexes: {existing_indexes}")
                except Exception as e:
                    print(f"Migration: Could not check existing indexes: {e}")
                    existing_indexes = set()

                # For PostgreSQL, just try to add the column - it will fail if exists
                try:
                    print("Migration: Attempting to add item_type column...")
                    await session.execute(text(
                        "ALTER TABLE auction_items ADD COLUMN IF NOT EXISTS item_type VARCHAR(20)"
                    ))
                    await session.commit()
                    print("Migration: item_type column added or already exists")
                except Exception as alter_err:
                    print(f"Migration: ALTER TABLE result: {alter_err}")
                    await session.rollback()

                # Try to create item_type index only if it doesn't exist
                if "ix_auction_items_item_type" not in existing_indexes:
                    try:
                        await session.execute(text(
                            "CREATE INDEX IF NOT EXISTS ix_auction_items_item_type ON auction_items (item_type)"
                        ))
                        await session.commit()
                        print("Migration: item_type index created")
                    except Exception as idx_err:
                        print(f"Migration: item_type index result: {idx_err}")
                        await session.rollback()
                else:
                    print("Migration: item_type index already exists, skipping")

                # Check if pg_trgm extension exists
                try:
                    result = await session.execute(text(
                        "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
                    ))
                    trgm_exists = result.scalar() is not None
                except Exception:
                    trgm_exists = False

                if not trgm_exists:
                    try:
                        print("Migration: Adding pg_trgm extension for fast search...")
                        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                        await session.commit()
                        print("Migration: pg_trgm extension added")
                    except Exception as ext_err:
                        print(f"Migration: pg_trgm extension result: {ext_err}")
                        await session.rollback()
                else:
                    print("Migration: pg_trgm extension already exists, skipping")

                # Create trigram index only if it doesn't exist
                if "ix_auction_items_title_trgm" not in existing_indexes:
                    try:
                        print("Migration: Creating trigram index on title (this may take a while)...")
                        await session.execute(text(
                            "CREATE INDEX IF NOT EXISTS ix_auction_items_title_trgm "
                            "ON auction_items USING gin (title gin_trgm_ops)"
                        ))
                        await session.commit()
                        print("Migration: title trigram index created")
                    except Exception as idx_err:
                        print(f"Migration: title trigram index result: {idx_err}")
                        await session.rollback()
                else:
                    print("Migration: title trigram index already exists, skipping")

                # Fix Card Hobby end_times that were stored without timezone conversion
                # They were stored as CST but treated as UTC, so they're 8 hours ahead
                try:
                    print("Migration: Checking for Card Hobby timezone fix...")
                    # Check if there are Card Hobby items with end_time in the future that should have ended
                    # This is a one-time fix - subtract 8 hours from all cardhobby end_times
                    # Only apply if we haven't done this already (check for a marker)
                    result = await session.execute(text(
                        "SELECT COUNT(*) FROM auction_items WHERE auction_house = 'cardhobby' "
                        "AND end_time > NOW() + INTERVAL '6 hours'"
                    ))
                    count = result.scalar()
                    if count and count > 0:
                        print(f"Migration: Found {count} Card Hobby items with potentially wrong timezone")
                        await session.execute(text(
                            "UPDATE auction_items "
                            "SET end_time = end_time - INTERVAL '8 hours' "
                            "WHERE auction_house = 'cardhobby' "
                            "AND end_time > NOW()"
                        ))
                        # Also update status for items that have now ended
                        await session.execute(text(
                            "UPDATE auction_items "
                            "SET status = 'Ended' "
                            "WHERE auction_house = 'cardhobby' "
                            "AND end_time < NOW() "
                            "AND status = 'Live'"
                        ))
                        await session.commit()
                        print("Migration: Card Hobby timezone fix applied")
                    else:
                        print("Migration: Card Hobby timezone already correct")
                except Exception as tz_err:
                    print(f"Migration: Card Hobby timezone fix result: {tz_err}")
                    await session.rollback()

                print("Migration: PostgreSQL migrations complete")

            else:
                # SQLite path
                check_query = text("PRAGMA table_info(auction_items)")
                result = await session.execute(check_query)
                columns = result.fetchall()
                column_exists = any(col[1] == 'item_type' for col in columns)

                if not column_exists:
                    print("Migration: Adding item_type column (SQLite)...")
                    await session.execute(text(
                        "ALTER TABLE auction_items ADD COLUMN item_type VARCHAR(20)"
                    ))
                    await session.execute(text(
                        "CREATE INDEX IF NOT EXISTS ix_auction_items_item_type ON auction_items (item_type)"
                    ))
                    await session.commit()
                    print("Migration: item_type column added successfully")
                else:
                    print("Migration: item_type column already exists (SQLite)")
    except Exception as e:
        # Don't let migration errors prevent startup
        print(f"Migration error (non-blocking): {e}")
        import traceback
        traceback.print_exc()


async def get_context(request: Request):
    """Build GraphQL context with optional authenticated user.

    If database connection fails, proceed as unauthenticated rather than
    failing the entire request. This makes the API more resilient during
    high load or connection pool exhaustion.
    """
    user = None
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            async for db in get_db():
                auth_service = AuthService(db)
                user = await auth_service.get_current_user(token)
                break
        except Exception as e:
            # Log but don't fail - proceed as unauthenticated
            print(f"Auth context error (proceeding as unauthenticated): {e}")

    return {"request": request, "user": user}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup - with error handling to allow app to start even if DB is temporarily unavailable
    try:
        await init_db()
    except Exception as e:
        print(f"WARNING: Database initialization error (non-fatal): {e}")

    # Run pending migrations (adds trigram indexes for fast search)
    try:
        await run_migrations()
    except Exception as e:
        print(f"WARNING: Migration error (non-fatal): {e}")

    # Start the scheduler
    scheduler.start()
    print("Scheduler started")

    # Configure default scheduled jobs if ENABLE_SCHEDULER is set
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        print("Configuring scheduled scraper jobs...")
        for job_id, config in SCRAPER_JOBS.items():
            scheduler.add_scraper_job(
                job_id=job_id,
                func=config["func"],
                interval_minutes=config["default_interval"],
            )
            print(f"  - {job_id}: every {config['default_interval']} minutes")

    yield

    # Shutdown
    print("Shutting down scheduler...")
    scheduler.shutdown()
    print("Shutdown complete")


app = FastAPI(
    title="CardWatch API",
    description="Auction aggregator for sports cards and collectibles",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
# In production, set CORS_ORIGINS env var to your frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routers
app.include_router(auth_router)
app.include_router(saved_searches_router)
app.include_router(ai_search_router)
app.include_router(scheduler_router)

# GraphQL endpoint with auth context
graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix="/graphql")


@app.get("/")
async def root():
    return {
        "message": "CardWatch API",
        "version": "0.3.0",
        "docs": "/docs",
        "graphql": "/graphql",
        "endpoints": {
            "auth": "/auth",
            "scheduler": "/api/scheduler",
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
