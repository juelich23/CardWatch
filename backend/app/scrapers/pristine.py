#!/usr/bin/env python3
"""
Pristine Auction Scraper
Fetches auction items from Pristine Auction by parsing HTML pages

Note: This scraper uses /auction/category/all which excludes 10-minute auctions.
10-minute auctions are a separate type at /auction/type/ten-minute
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
from app.utils.sport_detection import detect_sport_from_item


class PristineScraper:
    def __init__(self):
        self.base_url = "https://www.pristineauction.com"
        # URL format: /auction/page/{n}/per_page/60/category/all
        # Using 60 items per page for efficiency
        # Note: category/all excludes 10-minute auctions (they're a separate type)
        self.items_per_page = 60

    def extract_grading_info(self, title: str, subtitle: Optional[str]) -> dict:
        """Extract grading company, grade, and cert number from title"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        # Combine title and subtitle for searching
        full_text = f"{title} {subtitle or ''}"

        # Extract grading company and grade
        # Examples: "PSA 10", "BGS 9.5", "SGC 9", "BCCG 9"
        grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC|BCCG)\s+(\d+(?:\.\d+)?)\b'
        match = re.search(grading_pattern, full_text, re.IGNORECASE)

        if match:
            company = match.group(1)
            grade = match.group(2)

            # Normalize grading company names
            company_map = {
                'BGS': 'Beckett',
                'BECKETT': 'Beckett',
                'BCCG': 'Beckett'
            }
            result['grading_company'] = company_map.get(company.upper(), company)
            result['grade'] = grade

        return result

    def extract_category(self, title: str) -> Optional[str]:
        """Extract sport/category from title"""
        categories = {
            'Basketball': ['Basketball', 'NBA', 'Kobe', 'Jordan', 'LeBron', 'Curry'],
            'Football': ['Football', 'NFL', 'Mahomes', 'Brady'],
            'Baseball': ['Baseball', 'MLB', 'Trout', 'Ohtani'],
            'Hockey': ['Hockey', 'NHL', 'Gretzky'],
            'Soccer': ['Soccer', 'MLS', 'Messi', 'Ronaldo'],
            'Pokemon': ['Pokemon', 'Pikachu', 'Charizard'],
            'Magic The Gathering': ['Magic', 'MTG'],
            'Yu-Gi-Oh': ['Yu-Gi-Oh', 'YuGiOh']
        }

        title_upper = title.upper()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.upper() in title_upper:
                    return category

        return None

    def get_page_url(self, page_num: int) -> str:
        """Get URL for a specific page"""
        return f"{self.base_url}/auction/page/{page_num}/per_page/{self.items_per_page}/category/all"

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

    async def estimate_total_pages(self, client: httpx.AsyncClient) -> int:
        """Estimate total pages by checking specific page numbers"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }

        async def has_items(page: int) -> bool:
            url = self.get_page_url(page)
            try:
                resp = await client.get(url, headers=headers, timeout=15.0, follow_redirects=True)
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.find_all('div', class_='product', attrs={'data-pristine-product-venue-id': True})
                return len(items) > 0
            except:
                return False

        # Quick check at common boundaries
        # Based on ~60k items / 60 per page = ~1000 pages
        checkpoints = [500, 1000, 1500, 2000]
        last_with_items = 1

        for page in checkpoints:
            if await has_items(page):
                last_with_items = page
            else:
                break

        # Binary search between last_with_items and next checkpoint
        low = last_with_items
        high = last_with_items + 500

        while low < high:
            mid = (low + high + 1) // 2
            if await has_items(mid):
                low = mid
            else:
                high = mid - 1

        return low

    def parse_items(self, html: str) -> list:
        """Parse auction items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all product divs
        items = soup.find_all('div', class_='product', attrs={'data-pristine-product-venue-id': True})

        normalized_items = []

        for item_div in items:
            try:
                # Extract data attributes
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
                            # Try parsing from text
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

                # Find subtitle (grading/additional info)
                subtitle_elem = item_div.find('p', class_='subtitle')
                subtitle = subtitle_elem.get_text().strip() if subtitle_elem else None

                # Extract grading info
                grading_info = self.extract_grading_info(title, subtitle)

                # Extract category
                category = self.extract_category(title)

                # Lot number is the venue_id
                lot_number = venue_id

                # Detect sport from item content
                sport = detect_sport_from_item(title, subtitle, category).value

                normalized_item = {
                    "external_id": venue_id,
                    "lot_number": lot_number,
                    "cert_number": grading_info['cert_number'],
                    "sub_category": category,
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500] if title else "",
                    "description": subtitle,
                    "category": category,
                    "sport": sport,
                    "image_url": image_url,
                    "current_bid": current_bid,
                    "starting_bid": None,  # Not available in listing
                    "bid_count": 0,  # Not available in listing
                    "end_time": end_time,
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {
                        "venue_id": venue_id,
                        "subtitle": subtitle,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 150000, max_pages: int = 3000) -> list:
        """Main scraping function with pagination support

        Args:
            db: Database session
            max_items: Maximum items to scrape (default 150k to get all)
            max_pages: Maximum pages to scrape (default 3000 to get all)
        """
        print("🔍 Fetching items from Pristine Auction...")
        print(f"   Note: Excludes 10-minute auctions (separate type)")

        all_items = []

        async with httpx.AsyncClient() as client:
            # Estimate total pages
            print("📡 Estimating total pages...")
            total_pages = await self.estimate_total_pages(client)
            print(f"   Total pages available: {total_pages}")
            print(f"   Estimated items: ~{total_pages * self.items_per_page}")

            # Limit pages to scrape
            pages_to_scrape = min(max_pages, total_pages)
            print(f"   Will scrape {pages_to_scrape} pages (max_pages={max_pages})\n")

            # Parse items from each page
            consecutive_empty = 0
            for page_num in range(1, pages_to_scrape + 1):
                try:
                    if page_num % 50 == 1 or page_num == 1:
                        print(f"📦 Page {page_num}/{pages_to_scrape}... ({len(all_items)} items so far)")

                    page_url = self.get_page_url(page_num)
                    page_html = await self.fetch_page(client, page_url)

                    items = self.parse_items(page_html)

                    if len(items) == 0:
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            print(f"   Hit {consecutive_empty} consecutive empty pages, stopping")
                            break
                    else:
                        consecutive_empty = 0

                    if page_num % 50 == 1 or page_num == 1:
                        print(f"   Found {len(items)} items on page {page_num}")
                    all_items.extend(items)

                    if len(all_items) >= max_items:
                        print(f"   Reached max_items limit ({max_items})")
                        all_items = all_items[:max_items]
                        break

                    # Rate limiting - slight delay between requests
                    if page_num % 10 == 0:
                        await asyncio.sleep(0.5)

                except Exception as e:
                    print(f"   ⚠️ Error fetching page {page_num}: {e}")
                    continue

            normalized_items = all_items
            print(f"\n✅ Found {len(normalized_items)} total items")

            # Create or update auction
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
                    title="Pristine Auction - All Items",
                    status="active"
                )
                db.add(auction)
                await db.flush()

            print(f"✅ Auction ID: {auction.id}")

            # Save items to database
            print(f"\n💾 Saving {len(normalized_items)} items to database...")

            for item_data in normalized_items:
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == "pristine",
                        AuctionItem.external_id == item_data["external_id"]
                    )
                )
                existing_item = result.scalar_one_or_none()

                if existing_item:
                    # Update existing item
                    for key, value in item_data.items():
                        if key not in ['external_id', 'auction_house']:
                            setattr(existing_item, key, value)
                    existing_item.updated_at = datetime.utcnow()
                else:
                    # Create new item
                    item = AuctionItem(
                        auction_id=auction.id,
                        auction_house="pristine",
                        **item_data
                    )
                    db.add(item)

            await db.commit()
            print(f"✅ Saved {len(normalized_items)} items to database")

            # Count items with grading data
            graded_items = [item for item in normalized_items if item.get('grading_company')]
            print(f"   Items with grading data: {len(graded_items)}")

            return normalized_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Pristine Auction website is reachable"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = self.get_page_url(1)
                response = await client.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                    },
                    follow_redirects=True
                )
                if response.status_code == 200:
                    # Check if we can find auction items
                    soup = BeautifulSoup(response.text, 'html.parser')
                    items = soup.find_all('div', class_='product', attrs={'data-pristine-product-venue-id': True})
                    return HealthCheckResult(
                        healthy=True,
                        message="Pristine Auction is reachable",
                        details={"items_on_page": len(items), "items_per_page": self.items_per_page}
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
        python -m app.scrapers.pristine              # Full scrape (~60k items)
        python -m app.scrapers.pristine --test       # Test scrape (100 items)
        python -m app.scrapers.pristine --pages 10   # Scrape 10 pages (~600 items)
    """
    import sys

    # Parse args
    test_mode = '--test' in sys.argv
    pages_arg = None
    for i, arg in enumerate(sys.argv):
        if arg == '--pages' and i + 1 < len(sys.argv):
            pages_arg = int(sys.argv[i + 1])

    if test_mode:
        max_items = 100
        max_pages = 2
        print("🧪 Running in TEST mode (100 items, 2 pages)")
    elif pages_arg:
        max_items = pages_arg * 60
        max_pages = pages_arg
        print(f"📦 Running with {pages_arg} pages (~{max_items} items)")
    else:
        max_items = 150000
        max_pages = 3000
        print("🚀 Running FULL scrape (all items)")

    # Initialize database
    await init_db()

    scraper = PristineScraper()

    # Get database session
    async for db in get_db():
        items = await scraper.scrape(db, max_items=max_items, max_pages=max_pages)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
