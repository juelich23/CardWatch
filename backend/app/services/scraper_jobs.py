"""
Scraper job definitions for scheduled execution.
Each function handles its own database session management.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select, text

from app.config import get_settings
from app.models import Auction, AuctionItem

logger = logging.getLogger(__name__)

# Lazy-loaded engine and session factory
_engine = None
_async_session = None


def get_db_session():
    """Get database session factory."""
    global _engine, _async_session
    if _engine is None:
        settings = get_settings()

        # Transform database URL for asyncpg driver (same as database.py)
        database_url = settings.database_url
        is_postgres = database_url.startswith("postgresql") or database_url.startswith("postgres://")

        if is_postgres:
            # Use psycopg (psycopg3) instead of asyncpg for better pgbouncer compatibility
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
            elif "+asyncpg" in database_url:
                database_url = database_url.replace("+asyncpg", "+psycopg")
            elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        engine_kwargs = {
            "echo": False,
        }

        if is_postgres:
            # Use NullPool - let pgbouncer handle connection pooling
            # psycopg3 handles pgbouncer transaction mode natively
            engine_kwargs.update({
                "poolclass": NullPool,
                "connect_args": {
                    "prepare_threshold": None,
                },
            })
            print(f"[SCRAPER_JOBS CONFIG v3] Using psycopg driver with NullPool")

        _engine = create_async_engine(database_url, **engine_kwargs)
        _async_session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session


async def scrape_cardhobby(max_items: int = 2000, min_price: float = 100.0):
    """
    Scrape CardHobby auctions.

    Args:
        max_items: Maximum items to fetch
        min_price: Minimum current bid price filter
    """
    import httpx
    from app.utils.sport_detection import detect_sport_from_item

    logger.info(f"Starting CardHobby scrape (max_items={max_items}, min_price=${min_price})")
    start_time = datetime.utcnow()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Origin': 'https://www.cardhobby.com',
        'Referer': 'https://www.cardhobby.com/',
    }

    def parse_price(price_str):
        if not price_str:
            return 0.0
        try:
            return float(str(price_str).replace(',', ''))
        except:
            return 0.0

    all_items = {}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            page = 1
            while len(all_items) < max_items:
                payload = {
                    "userId": "",
                    "pageIndex": page,
                    "pageSize": 100,
                    "searchKey": "",
                    "searchJson": '[{"Key":"Status","Value":1},{"Key":"ByWay","Value":"2"}]',
                    "sort": "LowestPrice",
                    "sortType": "desc",
                    "lag": "en",
                    "device": "Web",
                    "version": 1,
                    "appname": "Card Hobby"
                }

                response = await client.post(
                    "https://gatewayapi.cardhobby.com/solr/NewCommodity/SearchCommodityPost",
                    json=payload
                )
                data = response.json()
                items = data.get("data", {}).get("PagedMarketItemList", [])

                if not items:
                    break

                for item in items:
                    current_bid = parse_price(item.get("USD_LowestPrice", 0))
                    starting_price = parse_price(item.get("USD_Price", 0))

                    if current_bid < min_price:
                        continue

                    end_time_str = item.get("EffectiveDate", "")
                    try:
                        end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        end_time = None

                    if end_time and end_time < datetime.utcnow():
                        continue

                    ext_id = str(item.get("ID"))
                    all_items[ext_id] = {
                        "external_id": ext_id,
                        "title": item.get("Title", ""),
                        "image_url": item.get("TitImg", ""),
                        "current_bid": current_bid,
                        "starting_bid": starting_price,
                        "bid_count": item.get("PriceCount", 0),
                        "end_time": end_time,
                        "lot_number": item.get("Code", ""),
                        "status": "Live",
                        "item_url": f"https://www.cardhobby.com/#/carddetails/{item.get('ID')}",
                    }

                    if len(all_items) >= max_items:
                        break

                # Check if we've hit items under threshold
                if items:
                    last_bid = parse_price(items[-1].get("USD_LowestPrice", 0))
                    if last_bid < min_price:
                        break

                page += 1
                await asyncio.sleep(0.2)

        items_list = list(all_items.values())
        logger.info(f"Fetched {len(items_list)} CardHobby items")

        # Save to database
        async_session = get_db_session()
        async with async_session() as db:
            # Get or create auction record
            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == "cardhobby",
                    Auction.external_id == "cardhobby-current"
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                auction = Auction(
                    auction_house="cardhobby",
                    external_id="cardhobby-current",
                    title="CardHobby Current Auctions",
                    status="active",
                )
                db.add(auction)
                await db.flush()

            # Upsert items (update existing, insert new)
            updated = 0
            inserted = 0

            for item_data in items_list:
                # Check if item exists
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == "cardhobby",
                        AuctionItem.external_id == item_data["external_id"]
                    )
                )
                existing = result.scalar_one_or_none()

                sport = detect_sport_from_item(title=item_data.get("title", ""), category="")
                sport_value = sport.value if hasattr(sport, 'value') else str(sport)

                if existing:
                    # Update existing item
                    existing.current_bid = item_data["current_bid"]
                    existing.bid_count = item_data["bid_count"]
                    existing.end_time = item_data["end_time"]
                    existing.status = item_data["status"]
                    existing.updated_at = datetime.utcnow()
                    updated += 1
                else:
                    # Insert new item
                    db_item = AuctionItem(
                        auction_id=auction.id,
                        external_id=item_data["external_id"],
                        auction_house="cardhobby",
                        title=item_data["title"],
                        image_url=item_data.get("image_url"),
                        current_bid=item_data.get("current_bid"),
                        starting_bid=item_data.get("starting_bid"),
                        bid_count=item_data.get("bid_count"),
                        end_time=item_data.get("end_time"),
                        lot_number=item_data.get("lot_number"),
                        status=item_data.get("status"),
                        item_url=item_data.get("item_url"),
                        sport=sport_value,
                        category="Trading Cards",
                    )
                    db.add(db_item)
                    inserted += 1

            # Mark ended auctions
            await db.execute(
                text("""
                    UPDATE auction_items
                    SET status = 'Ended'
                    WHERE auction_house = 'cardhobby'
                    AND end_time < :now
                    AND status != 'Ended'
                """),
                {"now": datetime.utcnow()}
            )

            await db.commit()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"CardHobby scrape complete: {inserted} new, {updated} updated in {duration:.1f}s")

            return {"inserted": inserted, "updated": updated, "duration": duration}

    except Exception as e:
        logger.error(f"CardHobby scrape failed: {e}")
        raise


async def scrape_goldin(max_items: int = 1000):
    """Scrape Goldin auctions."""
    logger.info("Starting Goldin scrape")
    # Import here to avoid circular imports
    from app.scrapers import GoldinHTTPScraper

    async_session = get_db_session()
    async with async_session() as db:
        try:
            scraper = GoldinHTTPScraper(db)
            items = await scraper.scrape_auction_items(max_items=max_items)
            await db.commit()
            logger.info(f"Goldin scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Goldin scrape failed: {e}")
            raise


async def scrape_fanatics(max_items: int = 1000):
    """Scrape Fanatics auctions."""
    logger.info("Starting Fanatics scrape")
    from app.scrapers import FanaticsScraper

    async_session = get_db_session()
    async with async_session() as db:
        try:
            scraper = FanaticsScraper(db)
            items = await scraper.scrape_auction_items(max_items=max_items)
            await db.commit()
            logger.info(f"Fanatics scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Fanatics scrape failed: {e}")
            raise


async def scrape_heritage(max_items: int = 1000):
    """Scrape Heritage auctions."""
    logger.info("Starting Heritage scrape")
    from app.scrapers import HeritageScraper

    async_session = get_db_session()
    async with async_session() as db:
        try:
            scraper = HeritageScraper(db)
            items = await scraper.scrape_auction_items(max_items=max_items)
            await db.commit()
            logger.info(f"Heritage scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Heritage scrape failed: {e}")
            raise


async def scrape_pristine():
    """Scrape Pristine auctions by category."""
    logger.info("Starting Pristine scrape (by category)")
    from app.scrapers import PristineScraper

    async_session = get_db_session()
    async with async_session() as db:
        try:
            scraper = PristineScraper()
            # Scrape all categories with up to 500 pages each (~30k items per category max)
            items = await scraper.scrape(db, categories=None, max_pages_per_category=500)
            logger.info(f"Pristine scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Pristine scrape failed: {e}")
            raise


async def cleanup_ended_auctions(days_old: int = 7):
    """
    Clean up ended auctions older than specified days.

    Args:
        days_old: Remove ended auctions older than this many days
    """
    logger.info(f"Starting cleanup of auctions ended more than {days_old} days ago")

    async_session = get_db_session()
    async with async_session() as db:
        try:
            result = await db.execute(
                text("""
                    DELETE FROM auction_items
                    WHERE status = 'Ended'
                    AND end_time < datetime('now', :days_ago)
                """),
                {"days_ago": f"-{days_old} days"}
            )

            deleted = result.rowcount
            await db.commit()

            logger.info(f"Cleanup complete: removed {deleted} old ended auctions")
            return {"deleted": deleted}

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise


# Job registry for easy access
SCRAPER_JOBS = {
    "cardhobby": {
        "func": scrape_cardhobby,
        "default_interval": 30,  # minutes
        "description": "Scrape CardHobby auctions",
    },
    "goldin": {
        "func": scrape_goldin,
        "default_interval": 30,
        "description": "Scrape Goldin auctions",
    },
    "fanatics": {
        "func": scrape_fanatics,
        "default_interval": 30,
        "description": "Scrape Fanatics auctions",
    },
    "heritage": {
        "func": scrape_heritage,
        "default_interval": 60,  # Less frequent - larger site
        "description": "Scrape Heritage auctions",
    },
    "pristine": {
        "func": scrape_pristine,
        "default_interval": 30,
        "description": "Scrape Pristine auctions",
    },
    "cleanup": {
        "func": cleanup_ended_auctions,
        "default_interval": 60 * 24,  # Daily
        "description": "Clean up old ended auctions",
    },
}
