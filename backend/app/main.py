import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from strawberry.fastapi import GraphQLRouter
from app.database import init_db, get_db
from app.config import get_settings
from app.graphql.schema import schema
from app.api.auth import router as auth_router
from app.api.saved_searches import router as saved_searches_router
from app.api.ai_search import router as ai_search_router
from app.api.scheduler import router as scheduler_router
from app.services.auth import AuthService
from app.services.scheduler import scheduler
from app.services.scraper_jobs import SCRAPER_JOBS

settings = get_settings()


async def get_context(request: Request):
    """Build GraphQL context with optional authenticated user"""
    user = None
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        async for db in get_db():
            auth_service = AuthService(db)
            user = await auth_service.get_current_user(token)
            break

    return {"request": request, "user": user}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    await init_db()
    print("Database initialized")

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
