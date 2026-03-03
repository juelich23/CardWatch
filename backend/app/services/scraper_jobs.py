"""
Scraper job definitions for scheduled execution.
Each function handles its own database session management.

Uses global scraper lock to prevent concurrent execution and
circuit breaker pattern to pause on repeated DB errors.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, text

from app.database import async_session_maker
from app.models import Auction, AuctionItem
from app.services.scheduler import with_scraper_lock

logger = logging.getLogger(__name__)


@with_scraper_lock
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
        except Exception:
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
                    except Exception:
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
        async with async_session_maker() as db:
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


@with_scraper_lock
async def scrape_goldin(max_items: int = 1000):
    """Scrape Goldin auctions."""
    logger.info("Starting Goldin scrape")
    # Import here to avoid circular imports
    from app.scrapers import GoldinHTTPScraper

    async with async_session_maker() as db:
        try:
            scraper = GoldinHTTPScraper(db)
            items = await scraper.scrape(db, max_items=max_items)
            logger.info(f"Goldin scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Goldin scrape failed: {e}")
            raise


@with_scraper_lock
async def scrape_fanatics(max_items: int = 1000):
    """Scrape Fanatics auctions."""
    logger.info("Starting Fanatics scrape")
    from app.scrapers import FanaticsScraper

    async with async_session_maker() as db:
        try:
            scraper = FanaticsScraper()
            items = await scraper.scrape(db, max_items=max_items)
            logger.info(f"Fanatics scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Fanatics scrape failed: {e}")
            raise


@with_scraper_lock
async def scrape_heritage(max_items: int = 1000):
    """Scrape Heritage auctions."""
    logger.info("Starting Heritage scrape")
    from app.scrapers import HeritageScraper

    async with async_session_maker() as db:
        try:
            scraper = HeritageScraper()
            items = await scraper.scrape(db, max_items=max_items)
            await db.commit()
            logger.info(f"Heritage scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Heritage scrape failed: {e}")
            raise


@with_scraper_lock
async def scrape_pristine():
    """Scrape Pristine auctions by category."""
    logger.info("Starting Pristine scrape (by category)")
    from app.scrapers import PristineScraper

    async with async_session_maker() as db:
        try:
            scraper = PristineScraper()
            # Scrape all categories with up to 500 pages each (~30k items per category max)
            items = await scraper.scrape(db, categories=None, max_pages_per_category=500)
            logger.info(f"Pristine scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"Pristine scrape failed: {e}")
            raise


@with_scraper_lock
async def cleanup_ended_auctions(days_old: int = 7):
    """
    Clean up ended auctions older than specified days.

    Args:
        days_old: Remove ended auctions older than this many days
    """
    logger.info(f"Starting cleanup of auctions ended more than {days_old} days ago")

    async with async_session_maker() as db:
        try:
            result = await db.execute(
                text("""
                    DELETE FROM auction_items
                    WHERE status = 'Ended'
                    AND end_time < NOW() - :days_old * INTERVAL '1 day'
                """),
                {"days_old": days_old}
            )

            deleted = result.rowcount
            await db.commit()

            logger.info(f"Cleanup complete: removed {deleted} old ended auctions")
            return {"deleted": deleted}

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise


@with_scraper_lock
async def scrape_alt(max_items: int = 10000):
    """
    Scrape Alt.xyz liquid auctions.

    Requires ALT_TYPESENSE_KEY environment variable to be set.
    Get the key from browser DevTools when loading app.alt.xyz/liquid-auctions.
    """
    import os
    from app.scrapers.alt import AltScraper

    api_key = os.getenv("ALT_TYPESENSE_KEY")
    if not api_key:
        logger.warning("ALT_TYPESENSE_KEY not set - skipping Alt.xyz scrape")
        return {"skipped": True, "reason": "no_api_key"}

    logger.info(f"Starting Alt.xyz scrape (max_items={max_items})")
    start_time = datetime.utcnow()

    async with async_session_maker() as db:
        try:
            scraper = AltScraper()
            items = await scraper.scrape(db, api_key=api_key, max_items=max_items)

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Alt.xyz scrape complete: {len(items)} items in {duration:.1f}s")

            return {
                "items_scraped": len(items),
                "duration_seconds": duration,
            }
        except Exception as e:
            logger.error(f"Alt.xyz scrape failed: {e}")
            raise


@with_scraper_lock
async def scrape_ebay(max_items: int = 5000):
    """Scrape eBay auctions via direct web scraping."""
    logger.info(f"Starting eBay scrape (max_items={max_items})")
    from app.scrapers.ebay import EbayScraper

    async with async_session_maker() as db:
        try:
            scraper = EbayScraper()
            items = await scraper.scrape(db, max_items=max_items)
            logger.info(f"eBay scrape complete: {len(items)} items")
            return {"items": len(items)}
        except Exception as e:
            logger.error(f"eBay scrape failed: {e}")
            raise


async def run_bidding_rules_job():
    """Scheduled job: run bidding rule matching for all users."""
    from app.services.bidding_engine import run_bidding_rules
    return await run_bidding_rules()


async def submit_pending_snipes_job():
    """Scheduled job: submit pending snipes to Gixen."""
    from app.services.bidding_engine import submit_pending_snipes
    return await submit_pending_snipes()


async def sync_gixen_status_job():
    """Scheduled job: sync Gixen snipe outcomes."""
    from app.services.bidding_engine import sync_gixen_status
    return await sync_gixen_status()


# Job registry for easy access
SCRAPER_JOBS = {
    "cardhobby": {
        "func": scrape_cardhobby,
        "default_interval": 60,  # every hour
        "description": "Scrape CardHobby auctions",
    },
    "goldin": {
        "func": scrape_goldin,
        "default_interval": 60,  # every hour
        "description": "Scrape Goldin auctions",
    },
    "fanatics": {
        "func": scrape_fanatics,
        "default_interval": 60,  # every hour
        "description": "Scrape Fanatics auctions",
    },
    "alt": {
        "func": scrape_alt,
        "default_interval": 60,  # every hour
        "description": "Scrape Alt.xyz liquid auctions",
    },
    # Heritage disabled - requires JavaScript rendering (ScraperAPI or Playwright with browsers)
    # "heritage": {
    #     "func": scrape_heritage,
    #     "default_interval": 120,
    #     "description": "Scrape Heritage auctions",
    # },
    "pristine": {
        "func": scrape_pristine,
        "default_interval": 240,  # every 4 hours - large scrape
        "description": "Scrape Pristine auctions",
    },
    "ebay": {
        "func": scrape_ebay,
        "default_interval": 30,  # every 30 minutes
        "description": "Scrape eBay auctions via Browse API",
    },
    "cleanup": {
        "func": cleanup_ended_auctions,
        "default_interval": 60 * 24,  # Daily
        "description": "Clean up old ended auctions",
    },
    "bidding_rules": {
        "func": run_bidding_rules_job,
        "default_interval": 10,  # every 10 minutes
        "description": "Match bidding rules to eBay items",
    },
    "bidding_submit": {
        "func": submit_pending_snipes_job,
        "default_interval": 5,  # every 5 minutes
        "description": "Submit pending snipes to Gixen",
    },
    "bidding_sync": {
        "func": sync_gixen_status_job,
        "default_interval": 15,  # every 15 minutes
        "description": "Sync Gixen snipe outcomes",
    },
}
