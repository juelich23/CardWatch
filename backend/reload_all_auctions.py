#!/usr/bin/env python3
"""
Master script to reload all auction house data
Runs all scrapers in sequence to populate the database with fresh data
"""
import asyncio
import os
import sys
from datetime import datetime

# Import all scrapers
from app.scrapers.goldin_httpx import GoldinHTTPScraper
from app.scrapers.fanatics import FanaticsScraper
from app.scrapers.pristine import PristineScraper
from app.scrapers.rea import REAScraper
from app.scrapers.heritage import HeritageScraper
from app.database import init_db, get_db


async def run_health_checks(houses: dict) -> dict:
    """Run health checks on all enabled scrapers"""
    print("\n🏥 Running health checks...")

    results = {}

    if houses.get('goldin'):
        scraper = GoldinHTTPScraper()
        result = await scraper.health_check()
        results['goldin'] = result
        print(f"   {result}")

    if houses.get('fanatics'):
        scraper = FanaticsScraper()
        result = await scraper.health_check()
        results['fanatics'] = result
        print(f"   {result}")

    if houses.get('pristine'):
        scraper = PristineScraper()
        result = await scraper.health_check()
        results['pristine'] = result
        print(f"   {result}")

    if houses.get('rea'):
        scraper = REAScraper()
        result = await scraper.health_check()
        results['rea'] = result
        print(f"   {result}")

    if houses.get('heritage'):
        scraper = HeritageScraper()
        result = await scraper.health_check()
        results['heritage'] = result
        print(f"   {result}")

    print("")
    return results


async def reload_all_auctions(
    clear_db: bool = False,
    goldin: bool = True,
    fanatics: bool = True,
    pristine: bool = True,
    rea: bool = True,
    heritage: bool = True,
    max_items_per_house: int = 1000,
    skip_health_check: bool = False
):
    """
    Reload all auction house data

    Args:
        clear_db: If True, deletes the existing database before reloading
        goldin: If True, scrape Goldin auctions
        fanatics: If True, scrape Fanatics auctions
        pristine: If True, scrape Pristine auctions
        rea: If True, scrape REA marketplace
        heritage: If True, scrape Heritage auctions
        max_items_per_house: Maximum items to fetch per auction house
        skip_health_check: If True, skip health checks before scraping
    """
    start_time = datetime.now()

    print("=" * 80)
    print("🔄 RELOADING ALL AUCTION DATA")
    print("=" * 80)
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Run health checks first
    houses = {
        'goldin': goldin,
        'fanatics': fanatics,
        'pristine': pristine,
        'rea': rea,
        'heritage': heritage
    }

    if not skip_health_check:
        health_results = await run_health_checks(houses)
        unhealthy = [h for h, r in health_results.items() if not r.healthy]
        if unhealthy:
            print(f"⚠️  Warning: {len(unhealthy)} scraper(s) failed health check: {', '.join(unhealthy)}")
            print("   Continuing anyway - errors will be handled per-scraper\n")

    # Handle database clearing
    if clear_db:
        db_path = "auction_data.db"
        if os.path.exists(db_path):
            print(f"🗑️  Deleting existing database: {db_path}")
            os.remove(db_path)
            print("✅ Database deleted\n")
        else:
            print(f"ℹ️  No existing database found at {db_path}\n")

    # Initialize database
    print("🔧 Initializing database...")
    await init_db()
    print("✅ Database initialized\n")

    # Track results
    results = {
        'goldin': {'enabled': goldin, 'items': 0, 'error': None},
        'fanatics': {'enabled': fanatics, 'items': 0, 'error': None},
        'pristine': {'enabled': pristine, 'items': 0, 'error': None},
        'rea': {'enabled': rea, 'items': 0, 'error': None},
        'heritage': {'enabled': heritage, 'items': 0, 'error': None},
    }

    # Get database session
    async for db in get_db():
        # 1. Goldin
        if goldin:
            print("\n" + "=" * 80)
            print("📦 GOLDIN AUCTIONS")
            print("=" * 80)
            try:
                scraper = GoldinHTTPScraper()
                items = await scraper.scrape(db, max_items=max_items_per_house)
                results['goldin']['items'] = len(items)
            except Exception as e:
                print(f"❌ Error scraping Goldin: {e}")
                results['goldin']['error'] = str(e)

        # 2. Fanatics
        if fanatics:
            print("\n" + "=" * 80)
            print("📦 FANATICS COLLECT")
            print("=" * 80)
            try:
                scraper = FanaticsScraper()
                items = await scraper.scrape(db, max_items=max_items_per_house)
                results['fanatics']['items'] = len(items)
            except Exception as e:
                print(f"❌ Error scraping Fanatics: {e}")
                results['fanatics']['error'] = str(e)

        # 3. Pristine
        if pristine:
            print("\n" + "=" * 80)
            print("📦 PRISTINE AUCTION")
            print("=" * 80)
            try:
                scraper = PristineScraper()
                items = await scraper.scrape(db, max_items=max_items_per_house)
                results['pristine']['items'] = len(items)
            except Exception as e:
                print(f"❌ Error scraping Pristine: {e}")
                results['pristine']['error'] = str(e)

        # 4. REA
        if rea:
            print("\n" + "=" * 80)
            print("📦 REA MARKETPLACE")
            print("=" * 80)
            try:
                scraper = REAScraper()
                items = await scraper.scrape(db, max_items=max_items_per_house, max_pages=10)
                results['rea']['items'] = len(items)
            except Exception as e:
                print(f"❌ Error scraping REA: {e}")
                results['rea']['error'] = str(e)

        # 5. Heritage
        if heritage:
            print("\n" + "=" * 80)
            print("📦 HERITAGE AUCTIONS")
            print("=" * 80)
            try:
                scraper = HeritageScraper()
                items = await scraper.scrape(db, max_items=max_items_per_house, max_pages=10)
                results['heritage']['items'] = len(items)
            except Exception as e:
                print(f"❌ Error scraping Heritage: {e}")
                results['heritage']['error'] = str(e)

    # Print summary
    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    total_items = 0
    for house, data in results.items():
        if data['enabled']:
            status = "✅" if data['error'] is None else "❌"
            items_str = f"{data['items']:,} items" if data['error'] is None else f"Error: {data['error']}"
            print(f"{status} {house.upper():12s} - {items_str}")
            if data['error'] is None:
                total_items += data['items']

    print(f"\n📈 Total items fetched: {total_items:,}")
    print(f"⏱️  Total time: {duration.total_seconds():.1f} seconds")
    print(f"🏁 Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def main():
    """Entry point with command-line argument support"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Reload all auction house data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reload all auction houses with default settings
  python reload_all_auctions.py

  # Clear database and reload all
  python reload_all_auctions.py --clear

  # Only reload Goldin and Fanatics
  python reload_all_auctions.py --only goldin fanatics

  # Skip Pristine and Heritage
  python reload_all_auctions.py --skip pristine heritage

  # Fetch 500 items per house
  python reload_all_auctions.py --max-items 500

  # Skip health checks
  python reload_all_auctions.py --no-health-check
        """
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='Delete the database before reloading'
    )

    parser.add_argument(
        '--only',
        nargs='+',
        choices=['goldin', 'fanatics', 'pristine', 'rea', 'heritage'],
        help='Only scrape specified auction houses'
    )

    parser.add_argument(
        '--skip',
        nargs='+',
        choices=['goldin', 'fanatics', 'pristine', 'rea', 'heritage'],
        help='Skip specified auction houses'
    )

    parser.add_argument(
        '--max-items',
        type=int,
        default=5000,
        help='Maximum items to fetch per auction house (default: 5000)'
    )

    parser.add_argument(
        '--no-health-check',
        action='store_true',
        help='Skip health checks before scraping'
    )

    args = parser.parse_args()

    # Determine which houses to scrape
    houses = {
        'goldin': True,
        'fanatics': True,
        'pristine': True,
        'rea': True,
        'heritage': True,
    }

    if args.only:
        # If --only is specified, disable all except those listed
        houses = {house: house in args.only for house in houses}

    if args.skip:
        # If --skip is specified, disable those listed
        for house in args.skip:
            houses[house] = False

    # Run the reload
    asyncio.run(reload_all_auctions(
        clear_db=args.clear,
        goldin=houses['goldin'],
        fanatics=houses['fanatics'],
        pristine=houses['pristine'],
        rea=houses['rea'],
        heritage=houses['heritage'],
        max_items_per_house=args.max_items,
        skip_health_check=args.no_health_check
    ))


if __name__ == "__main__":
    main()
