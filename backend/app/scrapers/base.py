from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, TypeVar, Any
from functools import wraps
import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar('T')


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (httpx.HTTPError, httpx.TimeoutException, ConnectionError)
):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"   ⚠️ Attempt {attempt + 1} failed: {e}. Retrying in {current_delay:.1f}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"   ❌ All {max_retries + 1} attempts failed")

            raise last_exception
        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter using token bucket algorithm"""

    def __init__(self, requests_per_second: float = 10.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_request_time

            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)

            self.last_request_time = asyncio.get_event_loop().time()


class HealthCheckResult:
    """Result of a scraper health check"""

    def __init__(self, healthy: bool, message: str, details: Optional[Dict] = None):
        self.healthy = healthy
        self.message = message
        self.details = details or {}

    def __repr__(self):
        status = "✅" if self.healthy else "❌"
        return f"{status} {self.message}"


class BaseScraper(ABC):
    """Base class for all auction house scrapers"""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.auction_house_name = "unknown"
        self.rate_limiter = RateLimiter(requests_per_second=10.0)

    @abstractmethod
    async def scrape(self, db: AsyncSession, max_items: int = 1000) -> List[Dict]:
        """
        Main scraping entry point. Scrapes items and saves to database.

        Args:
            db: Database session
            max_items: Maximum number of items to scrape

        Returns:
            List of scraped item dictionaries
        """
        pass

    @abstractmethod
    async def scrape_active_auctions(self) -> List[Dict]:
        """
        Scrape all active auctions from the auction house.
        Returns list of auction data dictionaries.
        """
        pass

    @abstractmethod
    async def scrape_auction_items(self, auction_id: str = None) -> List[Dict]:
        """
        Scrape all items from a specific auction (or all auctions if no ID provided).
        Returns list of item data dictionaries.
        """
        pass

    @abstractmethod
    async def get_item_details(self, item_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific item.
        Returns item data dictionary or None if not found.
        """
        pass

    async def health_check(self) -> HealthCheckResult:
        """
        Check if the scraper can connect to its target and fetch data.
        Override in subclasses for specific health checks.

        Returns:
            HealthCheckResult indicating scraper health
        """
        return HealthCheckResult(
            healthy=True,
            message=f"{self.auction_house_name} scraper base health check passed"
        )

    async def save_to_database(self, items: List[Dict]):
        """
        Save scraped items to the database.
        Handles deduplication, updates, and item type classification.
        """
        from app.models import AuctionItem
        from sqlalchemy import select
        from datetime import datetime
        from app.utils.item_type_detection import detect_item_type_from_dict

        for item_data in items:
            # Auto-classify item type if not already set
            if not item_data.get("item_type"):
                item_type = detect_item_type_from_dict(item_data)
                item_data["item_type"] = item_type.value

            # Check if item already exists
            result = await self.db.execute(
                select(AuctionItem).where(
                    AuctionItem.auction_house == self.auction_house_name,
                    AuctionItem.external_id == item_data.get("external_id")
                )
            )
            existing_item = result.scalar_one_or_none()

            if existing_item:
                # Update existing item
                for key, value in item_data.items():
                    if hasattr(existing_item, key):
                        setattr(existing_item, key, value)
                existing_item.updated_at = datetime.utcnow()
            else:
                # Create new item
                new_item = AuctionItem(
                    auction_house=self.auction_house_name,
                    **item_data
                )
                self.db.add(new_item)

        await self.db.commit()
