#!/usr/bin/env python3
"""
Pristine Auction Scraper
Fetches auction items from Pristine Auction by parsing HTML pages
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
        # Scrape ALL items (cards, memorabilia, autographs, jerseys, etc.)
        self.all_items_url = f"{self.base_url}/auction/category/all"

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

    def get_total_pages(self, html: str) -> int:
        """Extract total pages from pagination"""
        soup = BeautifulSoup(html, 'html.parser')

        # Look for pagination links
        pagination = soup.find('ul', class_='pagination')
        if pagination:
            # Find all page number links
            page_links = pagination.find_all('a', href=True)
            max_page = 1
            for link in page_links:
                href = link.get('href', '')
                page_match = re.search(r'page=(\d+)', href)
                if page_match:
                    page_num = int(page_match.group(1))
                    max_page = max(max_page, page_num)
            return max_page

        return 1

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

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function with pagination support"""
        print("🔍 Fetching items from Pristine Auction...")

        all_items = []

        async with httpx.AsyncClient() as client:
            # Fetch first page to get total pages
            print("📡 Fetching first page...")
            html = await self.fetch_page(client, self.all_items_url)

            # Get total pages
            total_pages = self.get_total_pages(html)
            print(f"   Total pages available: {total_pages}")

            # Limit pages to scrape
            pages_to_scrape = min(max_pages, total_pages)
            print(f"   Will scrape {pages_to_scrape} pages (max_pages={max_pages})\n")

            # Parse items from each page
            for page_num in range(1, pages_to_scrape + 1):
                try:
                    print(f"📦 Page {page_num}/{pages_to_scrape}...")

                    if page_num == 1:
                        page_html = html
                    else:
                        page_url = f"{self.all_items_url}?page={page_num}"
                        page_html = await self.fetch_page(client, page_url)
                        await asyncio.sleep(1)  # Rate limiting

                    items = self.parse_items(page_html)
                    print(f"   Found {len(items)} items on page {page_num}")
                    all_items.extend(items)

                    if len(all_items) >= max_items:
                        print(f"   Reached max_items limit ({max_items})")
                        all_items = all_items[:max_items]
                        break

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
                response = await client.get(
                    self.all_items_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                    },
                    follow_redirects=True
                )
                if response.status_code == 200:
                    # Check if we can find auction items
                    soup = BeautifulSoup(response.text, 'html.parser')
                    items = soup.find_all('div', class_='product')
                    return HealthCheckResult(
                        healthy=True,
                        message="Pristine Auction is reachable",
                        details={"items_on_page": len(items)}
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
    """Entry point for running the scraper"""
    # Initialize database
    await init_db()

    scraper = PristineScraper()

    # Get database session
    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
