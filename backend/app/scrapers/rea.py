#!/usr/bin/env python3
"""
REA (Robert Edward Auctions) Marketplace Scraper
Fetches "Buy It Now" items from REA marketplace by parsing HTML pages
"""

import asyncio
import httpx
import re
import json
from datetime import datetime
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult, retry_async
from app.utils.sport_detection import detect_sport_from_item


class REAScraper:
    def __init__(self):
        self.base_url = "https://bid.collectrea.com"
        self.marketplace_url = f"{self.base_url}/marketplace"

    def extract_grading_info(self, title: str) -> dict:
        """Extract grading company, grade, and cert number from title"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        # Extract PSA grading - more comprehensive patterns
        # Examples: "PSA NM-MT 8", "PSA GEM MINT 10", "PSA MINT 9", "PSA GOOD 2"
        psa_pattern = r'\bPSA\s+((?:GEM\s+)?(?:MINT|NM-MT|NM|EX-MT|EX|VG-EX|VG|GOOD|FAIR|POOR)(?:\s*\+)?)\s+(\d+(?:\.\d+)?)\b'
        psa_match = re.search(psa_pattern, title, re.IGNORECASE)

        if psa_match:
            result['grading_company'] = 'PSA'
            result['grade'] = psa_match.group(2)
            return result

        # Extract BGS/Beckett grading
        bgs_pattern = r'\b(BGS|Beckett|BCCG)\s+((?:GEM\s+)?MINT|PRISTINE)\s+(\d+(?:\.\d+)?)\b'
        bgs_match = re.search(bgs_pattern, title, re.IGNORECASE)

        if bgs_match:
            company = bgs_match.group(1)
            company_map = {
                'BGS': 'Beckett',
                'BECKETT': 'Beckett',
                'BCCG': 'Beckett'
            }
            result['grading_company'] = company_map.get(company.upper(), 'Beckett')
            result['grade'] = bgs_match.group(3)
            return result

        # Extract SGC grading
        sgc_pattern = r'\bSGC\s+(\d+(?:\.\d+)?)\b'
        sgc_match = re.search(sgc_pattern, title, re.IGNORECASE)

        if sgc_match:
            result['grading_company'] = 'SGC'
            result['grade'] = sgc_match.group(1)
            return result

        # Extract CGC grading
        cgc_pattern = r'\bCGC\s+(\d+(?:\.\d+)?)\b'
        cgc_match = re.search(cgc_pattern, title, re.IGNORECASE)

        if cgc_match:
            result['grading_company'] = 'CGC'
            result['grade'] = cgc_match.group(1)
            return result

        return result

    def extract_category(self, title: str) -> Optional[str]:
        """Extract sport/category from title"""
        categories = {
            'Basketball': ['Basketball', 'NBA', 'Jordan', 'Kobe', 'LeBron', 'Curry'],
            'Football': ['Football', 'NFL', 'Brady', 'Mahomes'],
            'Baseball': ['Baseball', 'MLB', 'Topps', 'Ruth', 'Mantle', 'Griffey'],
            'Hockey': ['Hockey', 'NHL', 'Gretzky', 'Lemieux'],
            'Soccer': ['Soccer', 'MLS', 'Messi', 'Ronaldo'],
            'TCG': ['Pokemon', 'Magic', 'MTG', 'Yu-Gi-Oh'],
        }

        title_upper = title.upper()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.upper() in title_upper:
                    return category

        return None

    def parse_alpine_data(self, x_data_str: str) -> dict:
        """Parse Alpine.js x-data attribute to extract product info"""
        result = {}

        # Extract productId
        product_id_match = re.search(r'productId:\s*(\d+)', x_data_str)
        if product_id_match:
            result['product_id'] = int(product_id_match.group(1))

        # Extract price
        price_match = re.search(r'price:\s*([\d.]+)', x_data_str)
        if price_match:
            result['price'] = float(price_match.group(1))

        # Extract status
        status_match = re.search(r"status:\s*'(\w+)'", x_data_str)
        if status_match:
            result['status'] = status_match.group(1)

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

    def parse_items(self, html: str) -> list:
        """Parse marketplace items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all product divs with Livewire keys
        items = soup.find_all('div', attrs={'wire:key': re.compile(r'^pr_')})

        normalized_items = []

        for item_div in items:
            try:
                # Extract Alpine.js data
                x_data = item_div.get('x-data', '')
                alpine_data = self.parse_alpine_data(x_data)

                # Skip if no product ID found
                if 'product_id' not in alpine_data:
                    continue

                # Skip sold items
                if alpine_data.get('status') == 'sold':
                    print(f"   ⏭️  Skipping sold item MP# {alpine_data.get('product_id')}")
                    continue

                # Extract MP number
                mp_elem = item_div.find('p', class_=re.compile(r'text-center.*font-bold'))
                mp_number = None
                if mp_elem:
                    mp_text = mp_elem.get_text().strip()
                    mp_match = re.search(r'MP#\s*(\d+)', mp_text)
                    if mp_match:
                        mp_number = mp_match.group(1)

                # Extract title
                title_elem = item_div.find('h3', class_='text-base')
                title = None
                item_url = None
                if title_elem:
                    title_link = title_elem.find('a')
                    if title_link:
                        title = title_link.get_text().strip()
                        item_url = title_link.get('href')

                # Extract image
                img_elem = item_div.find('img')
                image_url = None
                if img_elem:
                    image_url = img_elem.get('src')
                    # Use higher quality image by removing size constraints
                    if image_url and 'c_fit,e_sharpen' in image_url:
                        # Replace with larger size
                        image_url = re.sub(r'c_fit,e_sharpen:\d+,h_\d+,w_\d+/', 'c_fit,h_500,w_500/', image_url)

                # Get price from Alpine data
                current_bid = alpine_data.get('price')

                # Extract grading info
                grading_info = self.extract_grading_info(title) if title else {'grading_company': None, 'grade': None, 'cert_number': None}

                # Extract category
                category = self.extract_category(title) if title else None

                # Use MP number as both lot_number and external_id
                external_id = mp_number or str(alpine_data.get('product_id'))

                # Detect sport from item content
                sport = detect_sport_from_item(title, None, category).value

                normalized_item = {
                    "external_id": external_id,
                    "lot_number": mp_number,
                    "cert_number": grading_info['cert_number'],
                    "sub_category": category,
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500] if title else "",
                    "description": None,  # Not available in listing
                    "category": category,
                    "sport": sport,
                    "image_url": image_url,
                    "current_bid": current_bid,
                    "starting_bid": current_bid,  # Buy It Now price
                    "bid_count": 0,  # Not a bid-based auction
                    "end_time": None,  # No end time for Buy It Now items
                    "status": "Live",  # Listed items are live
                    "item_url": item_url,
                    "raw_data": {
                        "product_id": alpine_data.get('product_id'),
                        "mp_number": mp_number,
                        "rea_status": alpine_data.get('status'),
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    def get_total_pages(self, html: str) -> int:
        """Extract total pages from pagination text"""
        soup = BeautifulSoup(html, 'html.parser')

        # Look for "Showing X to Y of Z matching items (N pages total)"
        pagination_text = soup.find('p', class_='text-sm')
        if pagination_text:
            text = pagination_text.get_text()
            pages_match = re.search(r'\((\d+)\s+pages total\)', text)
            if pages_match:
                return int(pages_match.group(1))

        # Fallback: try to parse from Livewire snapshot
        snapshot_div = soup.find('div', attrs={'wire:snapshot': True})
        if snapshot_div:
            try:
                import html as html_module
                snapshot_json = html_module.unescape(snapshot_div.get('wire:snapshot'))
                snapshot_data = json.loads(snapshot_json)
                max_items = snapshot_data.get('data', {}).get('max', 0)
                page_size = snapshot_data.get('data', {}).get('pageSize', 12)
                if max_items and page_size:
                    return (max_items + page_size - 1) // page_size  # Ceiling division
            except:
                pass

        return 1

    async def scrape(self, db: AsyncSession, max_items: int = 2000, max_pages: int = 50) -> list:
        """Main scraping function"""
        print("🔍 Fetching items from REA Marketplace...")

        all_items = []

        async with httpx.AsyncClient() as client:
            # Fetch first page to get total pages
            print("📡 Fetching first page...")
            url = f"{self.marketplace_url}?sortBy=Lot_Number:desc&pageSize=100"
            html = await self.fetch_page(client, url)

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
                        # Already fetched first page
                        page_html = html
                    else:
                        # Fetch subsequent pages
                        page_url = f"{self.marketplace_url}?sortBy=Lot_Number:desc&pageSize=100&page={page_num}"
                        page_html = await self.fetch_page(client, page_url)
                        # Small delay between requests
                        await asyncio.sleep(1)

                    # Parse items
                    items = self.parse_items(page_html)
                    print(f"   Found {len(items)} items on page {page_num}")
                    all_items.extend(items)

                    # Check if we've reached max_items
                    if len(all_items) >= max_items:
                        print(f"   Reached max_items limit ({max_items})")
                        all_items = all_items[:max_items]
                        break

                except Exception as e:
                    print(f"   ⚠️ Error fetching page {page_num}: {e}")
                    continue

            print(f"\n✅ Found {len(all_items)} total items")

            # Create or update auction
            print("\n📦 Creating/updating auction record...")
            auction_external_id = "rea-marketplace"

            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == "rea",
                    Auction.external_id == auction_external_id
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                auction = Auction(
                    auction_house="rea",
                    external_id=auction_external_id,
                    title="REA Marketplace - Buy It Now",
                    status="active"
                )
                db.add(auction)
                await db.flush()

            print(f"✅ Auction ID: {auction.id}")

            # Save items to database
            print(f"\n💾 Saving {len(all_items)} items to database...")

            for item_data in all_items:
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == "rea",
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
                        auction_house="rea",
                        **item_data
                    )
                    db.add(item)

            await db.commit()
            print(f"✅ Saved {len(all_items)} items to database")

            # Count items with grading data
            graded_items = [item for item in all_items if item.get('grading_company')]
            print(f"   Items with grading data: {len(graded_items)}")

            return all_items

    async def health_check(self) -> HealthCheckResult:
        """Check if REA Marketplace is reachable"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.marketplace_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                    },
                    follow_redirects=True
                )
                if response.status_code == 200:
                    # Check if we can find marketplace items
                    soup = BeautifulSoup(response.text, 'html.parser')
                    items = soup.find_all('div', attrs={'wire:key': re.compile(r'^pr_')})
                    return HealthCheckResult(
                        healthy=True,
                        message="REA Marketplace is reachable",
                        details={"items_on_page": len(items)}
                    )
                return HealthCheckResult(
                    healthy=False,
                    message=f"REA Marketplace returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"REA Marketplace unreachable: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper"""
    # Initialize database
    await init_db()

    scraper = REAScraper()

    # Get database session
    async for db in get_db():
        items = await scraper.scrape(db, max_items=2000, max_pages=50)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
