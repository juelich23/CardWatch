from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Database
    database_url: str = "sqlite+aiosqlite:///./auction_data.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API Keys
    alt_api_key: str = ""
    anthropic_api_key: str = ""

    # Note: Fanatics Algolia API key is now fetched dynamically via GraphQL

    # Goldin credentials
    goldin_email: str = ""
    goldin_password: str = ""

    # FastAPI
    secret_key: str = "change-this-in-production"
    debug: bool = True

    # CORS - comma-separated list of allowed origins
    # In production, set to your frontend URL(s)
    cors_origins: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Performance settings
    scraper_concurrent_requests: int = 10
    scraper_request_timeout: int = 30
    cache_ttl: int = 300  # 5 minutes

    # Proxy settings for scrapers that need it (Heritage, etc.)
    # Format: http://user:pass@host:port or http://host:port
    proxy_url: str = ""
    # ScraperAPI key (alternative to proxy_url)
    scraperapi_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()
