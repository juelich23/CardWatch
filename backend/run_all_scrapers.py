#!/usr/bin/env python3
"""
Run all auction house scrapers to populate the database
"""

import asyncio
import sys
from datetime import datetime

# Add parent to path
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from app.database import init_db, get_db

async def run_scraper(name, scraper_class, db, max_items=500):
    """Run a single scraper and return results"""
    print(f"\n{'='*60}")
    print(f"Running {name} scraper...")
    print(f"{'='*60}")

    try:
        scraper = scraper_class()
        items = await scraper.scrape(db, max_items=max_items)
        print(f"✅ {name}: {len(items)} items scraped")
        return len(items)
    except Exception as e:
        print(f"❌ {name} failed: {e}")
        import traceback
        traceback.print_exc()
        return 0

async def main():
    print(f"\n{'#'*60}")
    print(f"# Running All Scrapers - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # Initialize database
    await init_db()

    # Import all scrapers
    from app.scrapers.goldin_httpx import GoldinHTTPScraper
    from app.scrapers.fanatics import FanaticsScraper
    from app.scrapers.heritage import HeritageScraper
    from app.scrapers.pristine import PristineScraper
    from app.scrapers.rea import REAScraper
    from app.scrapers.lelands import LelandsScraper
    from app.scrapers.classic_auctions import ClassicAuctionsScraper
    from app.scrapers.memorylane import MemoryLaneScraper
    from app.scrapers.milehigh import MileHighScraper
    from app.scrapers.cleansweep import CleanSweepScraper
    from app.scrapers.rr_auction import RRAuctionScraper
    from app.scrapers.auction_of_champions import AuctionOfChampionsScraper
    from app.scrapers.sirius import SiriusScraper
    from app.scrapers.gregmorris import GregMorrisScraper
    from app.scrapers.queencity import QueenCityScraper
    from app.scrapers.detroitcity import DetroitCityScraper
    from app.scrapers.vsa import VSAScraper
    from app.scrapers.hunt import HuntAuctionsScraper
    from app.scrapers.loveofthegame import LoveOfTheGameScraper
    from app.scrapers.ebay import EbayScraper

    scrapers = [
        ("Goldin", GoldinHTTPScraper),
        ("Fanatics", FanaticsScraper),
        ("Heritage", HeritageScraper),
        ("Pristine", PristineScraper),
        ("REA", REAScraper),
        ("Lelands", LelandsScraper),
        ("Classic Auctions", ClassicAuctionsScraper),
        ("Memory Lane", MemoryLaneScraper),
        ("Mile High", MileHighScraper),
        ("Clean Sweep", CleanSweepScraper),
        ("RR Auction", RRAuctionScraper),
        ("Auction of Champions", AuctionOfChampionsScraper),
        ("Sirius Sports", SiriusScraper),
        ("Greg Morris Cards", GregMorrisScraper),
        ("Queen City Cards", QueenCityScraper),
        ("Detroit City Sports", DetroitCityScraper),
        ("VSA Auctions", VSAScraper),
        ("Hunt Auctions", HuntAuctionsScraper),
        ("Love of the Game", LoveOfTheGameScraper),
        ("eBay", EbayScraper),
    ]

    results = {}

    async for db in get_db():
        for name, scraper_class in scrapers:
            count = await run_scraper(name, scraper_class, db, max_items=10000)
            results[name] = count
        break  # Only need one db session

    # Print summary
    print(f"\n{'#'*60}")
    print("# SUMMARY")
    print(f"{'#'*60}")
    total = 0
    for name, count in results.items():
        status = "✅" if count > 0 else "❌"
        print(f"{status} {name}: {count} items")
        total += count

    print(f"\n📊 Total items scraped: {total}")
    print(f"✅ Scraping complete!")

if __name__ == "__main__":
    asyncio.run(main())
