#!/usr/bin/env python3
"""
Pristine Auction Scraper
Fetches auction items from Pristine Auction by scraping each category page.

Scrapes by category to get accurate category data for filtering.
Excludes 10-minute auctions (they're a separate auction type).
"""

import asyncio
import httpx
import re
from datetime import datetime
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult, retry_async


# Pristine categories with their URL slugs and mapping to our sport enum
# Valid sport values: BASKETBALL, BASEBALL, FOOTBALL, HOCKEY, SOCCER, GOLF, BOXING, RACING, OTHER
PRISTINE_CATEGORIES = {
    "baseball": {"name": "Baseball", "sport": "BASEBALL"},
    "basketball": {"name": "Basketball", "sport": "BASKETBALL"},
    "football": {"name": "Football", "sport": "FOOTBALL"},
    "hockey": {"name": "Hockey", "sport": "HOCKEY"},
    "soccer": {"name": "Soccer", "sport": "SOCCER"},
    "golf": {"name": "Golf", "sport": "GOLF"},
    "boxing-ufc": {"name": "Boxing & UFC", "sport": "BOXING"},
    "wrestling": {"name": "Wrestling", "sport": "OTHER"},
    "racing": {"name": "Racing", "sport": "RACING"},
    "other-sports": {"name": "Other Sports", "sport": "OTHER"},
    "trading-cards": {"name": "Trading Cards", "sport": "OTHER"},  # Mixed sports cards
    "pop-culture": {"name": "Pop Culture", "sport": "OTHER"},
    "music": {"name": "Music", "sport": "OTHER"},
    "historical": {"name": "Historical", "sport": "OTHER"},
    "comic-books": {"name": "Comic Books", "sport": "OTHER"},
    "coins-bullion": {"name": "Coins & Bullion", "sport": "OTHER"},
    "fine-art": {"name": "Art", "sport": "OTHER"},
}


class PristineScraper:
    def __init__(self):
        self.base_url = "https://www.pristineauction.com"
        self.items_per_page = 60

    def get_category_url(self, category_slug: str, page_num: int) -> str:
        """Get URL for a specific category and page"""
        return f"{self.base_url}/auction/page/{page_num}/per_page/{self.items_per_page}/category/{category_slug}"

    def extract_grading_info(self, title: str, subtitle: Optional[str]) -> dict:
        """Extract grading company, grade, and cert number from title"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        full_text = f"{title} {subtitle or ''}"

        # Match patterns like "PSA 10", "BGS 9.5", "SGC 9", "BCCG 9"
        grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC|BCCG)\s+(\d+(?:\.\d+)?)\b'
        match = re.search(grading_pattern, full_text, re.IGNORECASE)

        if match:
            company = match.group(1)
            grade = match.group(2)

            company_map = {
                'BGS': 'Beckett',
                'BECKETT': 'Beckett',
                'BCCG': 'Beckett'
            }
            result['grading_company'] = company_map.get(company.upper(), company.upper())
            result['grade'] = grade

        return result

    @retry_async(max_retries=3, delay=1.0)
    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        """Fetch a page with proper headers"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': self.base_url,
        }

        response = await client.get(url, headers=headers, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return response.text

    def parse_items(self, html: str, category_slug: str, category_info: dict) -> list:
        """Parse auction items from HTML with category data"""
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('div', class_='product', attrs={'data-pristine-product-venue-id': True})

        normalized_items = []

        for item_div in items:
            try:
                venue_id = item_div.get('data-pristine-product-venue-id')
                title = item_div.get('data-pristine-title', '')

                # Find image
                img = item_div.find('img', class_='img-thumbnail')
                image_url = img.get('src') if img else None

                # Find item URL
                link = item_div.find('a', class_='title')
                item_url = None
                if link and link.get('href'):
                    href = link.get('href')
                    item_url = f"{self.base_url}{href}" if href.startswith('/') else href

                # Find current bid
                high_bid_elem = item_div.find('p', class_='high-bid')
                current_bid = None
                if high_bid_elem:
                    bid_data = high_bid_elem.get('data-high-bid')
                    if bid_data:
                        try:
                            current_bid = float(bid_data)
                        except:
                            bid_text = high_bid_elem.get_text().strip()
                            bid_match = re.search(r'\$?([\d,]+\.?\d*)', bid_text)
                            if bid_match:
                                current_bid = float(bid_match.group(1).replace(',', ''))

                # Find end time
                end_time_elem = item_div.find('span', class_='end-time')
                end_time = None
                if end_time_elem:
                    timestamp = end_time_elem.get('data-pristine-end-time') or end_time_elem.get('data-timestamp')
                    if timestamp:
                        try:
                            end_time = datetime.fromtimestamp(int(timestamp))
                        except:
                            pass

                # Find subtitle
                subtitle_elem = item_div.find('p', class_='subtitle')
                subtitle = subtitle_elem.get_text().strip() if subtitle_elem else None

                # Extract grading info
                grading_info = self.extract_grading_info(title, subtitle)

                normalized_item = {
                    "external_id": venue_id,
                    "lot_number": venue_id,
                    "cert_number": grading_info['cert_number'],
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500] if title else "",
                    "description": subtitle,
                    # Use Pristine's category directly
                    "category": category_info["name"],
                    "sub_category": category_slug,
                    "sport": category_info["sport"],
                    "image_url": image_url,
                    "current_bid": current_bid,
                    "starting_bid": None,
                    "bid_count": 0,
                    "end_time": end_time,
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {
                        "venue_id": venue_id,
                        "subtitle": subtitle,
                        "pristine_category": category_slug,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape_category(
        self,
        client: httpx.AsyncClient,
        category_slug: str,
        category_info: dict,
        max_pages: int = 500
    ) -> list:
        """Scrape all items from a single category"""
        all_items = []
        consecutive_empty = 0
        page_num = 1

        while page_num <= max_pages:
            try:
                url = self.get_category_url(category_slug, page_num)
                html = await self.fetch_page(client, url)
                items = self.parse_items(html, category_slug, category_info)

                if len(items) == 0:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                else:
                    consecutive_empty = 0
                    all_items.extend(items)

                page_num += 1

                # Rate limiting
                if page_num % 10 == 0:
                    await asyncio.sleep(0.3)

            except Exception as e:
                print(f"      ⚠️ Error on page {page_num}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    break
                page_num += 1
                continue

        return all_items

    async def scrape(
        self,
        db: AsyncSession,
        categories: List[str] = None,
        max_pages_per_category: int = 500
    ) -> list:
        """Main scraping function - scrapes by category

        Args:
            db: Database session
            categories: List of category slugs to scrape (None = all)
            max_pages_per_category: Max pages per category (default 500 = 30k items)
        """
        print("🔍 Fetching items from Pristine Auction (by category)...")
        print(f"   Excludes 10-minute auctions")

        # Use all categories if none specified
        if categories is None:
            categories = list(PRISTINE_CATEGORIES.keys())

        print(f"   Categories to scrape: {len(categories)}")
        print()

        all_items = []
        category_counts = {}

        async with httpx.AsyncClient() as client:
            for i, category_slug in enumerate(categories, 1):
                category_info = PRISTINE_CATEGORIES.get(category_slug)
                if not category_info:
                    print(f"   ⚠️ Unknown category: {category_slug}")
                    continue

                print(f"📦 [{i}/{len(categories)}] Scraping {category_info['name']}...")

                items = await self.scrape_category(
                    client,
                    category_slug,
                    category_info,
                    max_pages_per_category
                )

                category_counts[category_info['name']] = len(items)
                all_items.extend(items)

                print(f"   ✓ Found {len(items)} items in {category_info['name']}")

                # Brief pause between categories
                await asyncio.sleep(0.5)

        print(f"\n✅ Found {len(all_items)} total items across {len(categories)} categories")

        # Print category breakdown
        print("\n📊 Category breakdown:")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"   {cat}: {count:,}")

        # Deduplicate by external_id (items might appear in multiple categories)
        seen_ids = set()
        unique_items = []
        duplicates = 0
        for item in all_items:
            if item["external_id"] not in seen_ids:
                seen_ids.add(item["external_id"])
                unique_items.append(item)
            else:
                duplicates += 1

        if duplicates > 0:
            print(f"\n   Removed {duplicates} duplicate items")
            print(f"   Unique items: {len(unique_items)}")

        # Create or update auction record
        print("\n📦 Creating/updating auction record...")
        auction_external_id = "pristine-all"

        result = await db.execute(
            select(Auction).where(
                Auction.auction_house == "pristine",
                Auction.external_id == auction_external_id
            )
        )
        auction = result.scalar_one_or_none()

        if not auction:
            auction = Auction(
                auction_house="pristine",
                external_id=auction_external_id,
                title="Pristine Auction",
                status="active"
            )
            db.add(auction)
            await db.flush()

        print(f"✅ Auction ID: {auction.id}")

        # Save items to database
        print(f"\n💾 Saving {len(unique_items)} items to database...")

        new_count = 0
        update_count = 0

        for item_data in unique_items:
            result = await db.execute(
                select(AuctionItem).where(
                    AuctionItem.auction_house == "pristine",
                    AuctionItem.external_id == item_data["external_id"]
                )
            )
            existing_item = result.scalar_one_or_none()

            if existing_item:
                for key, value in item_data.items():
                    if key not in ['external_id', 'auction_house']:
                        setattr(existing_item, key, value)
                existing_item.updated_at = datetime.utcnow()
                update_count += 1
            else:
                item = AuctionItem(
                    auction_id=auction.id,
                    auction_house="pristine",
                    **item_data
                )
                db.add(item)
                new_count += 1

        await db.commit()
        print(f"✅ Saved to database: {new_count} new, {update_count} updated")

        # Count graded items
        graded_items = [item for item in unique_items if item.get('grading_company')]
        print(f"   Items with grading data: {len(graded_items)}")

        return unique_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Pristine Auction website is reachable"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = self.get_category_url("baseball", 1)
                response = await client.get(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'},
                    follow_redirects=True
                )
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    items = soup.find_all('div', class_='product', attrs={'data-pristine-product-venue-id': True})
                    return HealthCheckResult(
                        healthy=True,
                        message="Pristine Auction is reachable",
                        details={"items_on_page": len(items), "categories": len(PRISTINE_CATEGORIES)}
                    )
                return HealthCheckResult(
                    healthy=False,
                    message=f"Pristine Auction returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Pristine Auction unreachable: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper

    Usage:
        python -m app.scrapers.pristine                    # Full scrape (all categories)
        python -m app.scrapers.pristine --test             # Test scrape (2 categories, 2 pages each)
        python -m app.scrapers.pristine --category baseball  # Scrape single category
    """
    import sys

    test_mode = '--test' in sys.argv

    # Check for single category
    single_category = None
    for i, arg in enumerate(sys.argv):
        if arg == '--category' and i + 1 < len(sys.argv):
            single_category = sys.argv[i + 1]

    if test_mode:
        categories = ["baseball", "basketball"]
        max_pages = 2
        print("🧪 Running in TEST mode (2 categories, 2 pages each)")
    elif single_category:
        categories = [single_category]
        max_pages = 500
        print(f"📦 Running single category: {single_category}")
    else:
        categories = None  # All categories
        max_pages = 500
        print("🚀 Running FULL scrape (all categories)")

    await init_db()

    scraper = PristineScraper()

    async for db in get_db():
        items = await scraper.scrape(
            db,
            categories=categories,
            max_pages_per_category=max_pages
        )

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
