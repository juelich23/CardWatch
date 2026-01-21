#!/usr/bin/env python3
"""
Sirius Sports Auctions Scraper
Fetches auction items from Sirius Sports Auctions.
Uses Playwright for browser-based scraping (similar platform to Classic Auctions).
"""

import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult
from app.utils.sport_detection import detect_sport_from_item


class SiriusScraper:
    def __init__(self):
        self.base_url = "https://siriussportsauctions.com"
        self.catalog_url = f"{self.base_url}/catalog.aspx"
        self.auction_house_name = "sirius"
        self._browser = None
        self._playwright = None

    def extract_grading_info(self, title: str) -> dict:
        """Extract grading company, grade, and cert number from title"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC|BCCG)\s+(?:[\w\-\+]+\s+)?(\d+(?:\.\d+)?)\b'
        match = re.search(grading_pattern, title, re.IGNORECASE)

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

    def extract_category(self, title: str) -> Optional[str]:
        """Extract sport/category from title"""
        title_upper = title.upper()

        if any(kw in title_upper for kw in ['BASEBALL', 'MLB', 'TOPPS', 'BOWMAN']):
            return 'Baseball'
        if any(kw in title_upper for kw in ['BASKETBALL', 'NBA']):
            return 'Basketball'
        if any(kw in title_upper for kw in ['FOOTBALL', 'NFL']):
            return 'Football'
        if any(kw in title_upper for kw in ['HOCKEY', 'NHL']):
            return 'Hockey'

        return 'Sports Cards'

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string"""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            return float(match.group(1).replace(',', ''))
        return None

    async def _ensure_browser(self):
        """Ensure Playwright browser is initialized"""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                channel="chrome"
            )

    async def _close_browser(self):
        """Close Playwright browser"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch_page(self, url: str) -> str:
        """Fetch a page using Playwright"""
        await self._ensure_browser()

        context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
            html = await page.content()
            return html
        finally:
            await page.close()
            await context.close()

    def parse_items(self, html: str) -> list:
        """Parse auction items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        normalized_items = []

        # Try different container patterns
        # Pattern 1: div.lot (like Classic Auctions)
        lots = soup.find_all('div', class_='lot')

        # Pattern 2: Look for item containers with lot numbers
        if not lots:
            lots = soup.find_all('div', class_=lambda x: x and ('item' in str(x).lower() or 'lot' in str(x).lower()))

        for lot_div in lots:
            try:
                # Extract lot number
                lot_number_elem = lot_div.find(['span', 'div'], class_=lambda x: x and 'lot' in str(x).lower() and 'number' in str(x).lower())
                if not lot_number_elem:
                    lot_number_elem = lot_div.find(['span', 'div'], id=lambda x: x and 'lot' in str(x).lower())
                lot_number = lot_number_elem.get_text().strip() if lot_number_elem else None

                # Extract title and URL
                title_link = lot_div.find('a', href=lambda x: x and ('lot' in str(x).lower() or 'item' in str(x).lower()))
                if not title_link:
                    title_link = lot_div.find('a')

                title = None
                item_url = None
                if title_link:
                    title = title_link.get_text().strip()
                    href = title_link.get('href')
                    item_url = f"{self.base_url}/{href}" if href and not href.startswith('http') else href

                if not title or len(title) < 5:
                    continue

                # Extract external ID from URL or lot number
                external_id = None
                if item_url:
                    id_match = re.search(r'[?&]id=(\d+)|LOT(\d+)|lot[_-]?(\d+)', item_url, re.IGNORECASE)
                    if id_match:
                        external_id = id_match.group(1) or id_match.group(2) or id_match.group(3)
                if not external_id and lot_number:
                    external_id = re.sub(r'[^\d]', '', lot_number)

                if not external_id:
                    continue

                # Extract image URL
                img_elem = lot_div.find('img')
                image_url = None
                if img_elem and img_elem.get('src'):
                    src = img_elem.get('src')
                    image_url = f"{self.base_url}/{src}" if src.startswith('/') else src

                # Extract bid info
                lot_text = lot_div.get_text()
                bids_count = 0
                min_bid = None
                current_bid = None
                status = "Live"

                # Look for bid patterns
                bids_match = re.search(r'(?:# ?Bids|Bids):\s*(\d+)', lot_text, re.IGNORECASE)
                if bids_match:
                    bids_count = int(bids_match.group(1))

                min_match = re.search(r'(?:Min|Starting|Open)\s*(?:Bid)?:\s*\$?([\d,]+)', lot_text, re.IGNORECASE)
                if min_match:
                    min_bid = float(min_match.group(1).replace(',', ''))

                current_match = re.search(r'(?:Current|High)\s*(?:Bid)?:\s*\$?([\d,]+)', lot_text, re.IGNORECASE)
                if current_match:
                    current_bid = float(current_match.group(1).replace(',', ''))

                final_match = re.search(r'(?:Final|Sold|Won).*?:\s*\$?([\d,]+)', lot_text, re.IGNORECASE)
                if final_match:
                    current_bid = float(final_match.group(1).replace(',', ''))
                    status = "Ended"

                # Skip ended items
                if status == "Ended":
                    continue

                if current_bid is None and min_bid:
                    current_bid = min_bid

                # Extract grading info
                grading_info = self.extract_grading_info(title)

                # Extract category
                category = self.extract_category(title)

                # Detect sport from item content
                sport = detect_sport_from_item(title, None, category).value

                normalized_item = {
                    "external_id": external_id,
                    "lot_number": lot_number,
                    "cert_number": grading_info['cert_number'],
                    "sub_category": category,
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500] if title else "",
                    "description": None,
                    "category": category,
                    "sport": sport,
                    "image_url": image_url,
                    "current_bid": current_bid,
                    "starting_bid": min_bid,
                    "bid_count": bids_count,
                    "end_time": None,
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {
                        "lot_number": lot_number,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    def get_pagination_info(self, soup: BeautifulSoup) -> dict:
        """Extract pagination information"""
        pagination_info = {
            'current_page': 1,
            'total_pages': 1,
            'total_items': 0
        }

        page_links = soup.find_all('a', href=lambda x: x and 'page=' in str(x))
        max_page = 1
        for link in page_links:
            href = link.get('href', '')
            page_match = re.search(r'page=(\d+)', href)
            if page_match:
                page_num = int(page_match.group(1))
                max_page = max(max_page, page_num)
        pagination_info['total_pages'] = max_page

        return pagination_info

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function with pagination support"""
        print("🔍 Fetching items from Sirius Sports Auctions...")

        all_items = []

        try:
            print("📡 Fetching catalog page (using Playwright)...")
            html = await self.fetch_page(self.catalog_url)

            soup = BeautifulSoup(html, 'html.parser')
            pagination_info = self.get_pagination_info(soup)
            print(f"   Total pages available: {pagination_info['total_pages']}")

            pages_to_scrape = min(max_pages, pagination_info['total_pages'])

            for page_num in range(1, pages_to_scrape + 1):
                try:
                    print(f"📦 Page {page_num}/{pages_to_scrape}...")

                    if page_num == 1:
                        page_html = html
                    else:
                        page_url = f"{self.catalog_url}?page={page_num}"
                        page_html = await self.fetch_page(page_url)
                        await asyncio.sleep(1)

                    items = self.parse_items(page_html)
                    print(f"   Found {len(items)} items on page {page_num}")
                    all_items.extend(items)

                    if len(all_items) >= max_items:
                        all_items = all_items[:max_items]
                        break

                except Exception as e:
                    print(f"   ⚠️ Error fetching page {page_num}: {e}")
                    continue

            normalized_items = all_items
            print(f"\n✅ Found {len(normalized_items)} total items")
        finally:
            await self._close_browser()

        # Create or update auction
        print("\n📦 Creating/updating auction record...")
        auction_external_id = "sirius-current"

        result = await db.execute(
            select(Auction).where(
                Auction.auction_house == self.auction_house_name,
                Auction.external_id == auction_external_id
            )
        )
        auction = result.scalar_one_or_none()

        if not auction:
            auction = Auction(
                auction_house=self.auction_house_name,
                external_id=auction_external_id,
                title="Sirius Sports Auctions",
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
                    AuctionItem.auction_house == self.auction_house_name,
                    AuctionItem.external_id == item_data["external_id"]
                )
            )
            existing_item = result.scalar_one_or_none()

            if existing_item:
                for key, value in item_data.items():
                    if key not in ['external_id', 'auction_house']:
                        setattr(existing_item, key, value)
                existing_item.updated_at = datetime.utcnow()
            else:
                item = AuctionItem(
                    auction_id=auction.id,
                    auction_house=self.auction_house_name,
                    **item_data
                )
                db.add(item)

        await db.commit()
        print(f"✅ Saved {len(normalized_items)} items to database")

        graded_items = [item for item in normalized_items if item.get('grading_company')]
        print(f"   Items with grading data: {len(graded_items)}")

        return normalized_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Sirius Sports Auctions is reachable"""
        try:
            html = await self.fetch_page(self.catalog_url)
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.find_all('div', class_='lot')

            if items:
                return HealthCheckResult(
                    healthy=True,
                    message="Sirius Sports Auctions is reachable",
                    details={"items_on_page": len(items)}
                )
            return HealthCheckResult(
                healthy=False,
                message="Sirius returned no items",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Sirius unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = SiriusScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
