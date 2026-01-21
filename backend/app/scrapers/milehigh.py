#!/usr/bin/env python3
"""
Mile High Card Company Scraper
Fetches auction items from Mile High Card Company (premium cards).
Uses Playwright for browser-based scraping.
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


class MileHighScraper:
    def __init__(self):
        self.base_url = "https://www.milehighcardco.com"
        self.catalog_url = f"{self.base_url}/Catalog.aspx"
        self.auction_house_name = "milehigh"
        self._browser = None
        self._playwright = None

    def extract_grading_info(self, title: str) -> dict:
        """Extract grading company, grade, and cert number from title"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        # Extract grading company and grade
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

        # Mile High is premium cards focused
        if any(kw in title_upper for kw in ['BASEBALL', 'MLB', 'TOPPS', 'T206', 'BOWMAN']):
            return 'Baseball'
        if any(kw in title_upper for kw in ['BASKETBALL', 'NBA']):
            return 'Basketball'
        if any(kw in title_upper for kw in ['FOOTBALL', 'NFL']):
            return 'Football'
        if any(kw in title_upper for kw in ['HOCKEY', 'NHL']):
            return 'Hockey'
        if any(kw in title_upper for kw in ['JERSEY', 'GAME-WORN', 'GAME WORN', 'SIGNED', 'AUTOGRAPH']):
            return 'Memorabilia'

        return 'Baseball'  # Default for Mile High Card Company

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string like '$27,584' or 'Min Bid: $5,000'"""
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
        """Fetch a page using Playwright (non-headless mode for WAF bypass)"""
        await self._ensure_browser()

        context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)  # Wait for JS to render
            html = await page.content()
            return html
        finally:
            await page.close()
            await context.close()

    def parse_items(self, html: str) -> list:
        """Parse auction items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all lot containers
        lots = soup.find_all('div', class_='lot')
        normalized_items = []

        for lot_div in lots:
            try:
                # Extract lot number
                lot_number_elem = lot_div.find('span', id='LotNumber')
                lot_number = lot_number_elem.get_text().strip() if lot_number_elem else None

                # Extract title and URL
                lot_name_elem = lot_div.find('span', id='LotName')
                title_link = lot_name_elem.find('a') if lot_name_elem else None
                title = title_link.get_text().strip() if title_link else None
                item_url = title_link.get('href') if title_link else None

                # Ensure full URL
                if item_url and not item_url.startswith('http'):
                    item_url = f"{self.base_url}{item_url}"

                # Extract external ID from URL (LOT######)
                external_id = None
                if item_url:
                    id_match = re.search(r'-LOT(\d+)\.aspx', item_url, re.IGNORECASE)
                    if id_match:
                        external_id = id_match.group(1)

                # Extract image URL
                img_elem = lot_div.find('img', class_='lotImage')
                image_url = None
                if img_elem and img_elem.get('src'):
                    src = img_elem.get('src')
                    image_url = f"{self.base_url}{src}" if src.startswith('/') else src

                # Extract bid info from lotData
                lot_data = lot_div.find('div', class_='lotData')
                bids_count = None
                min_bid = None
                current_bid = None
                status = "Live"

                if lot_data:
                    spans = lot_data.find_all('span')
                    for span in spans:
                        text = span.get_text().strip()

                        # Extract number of bids
                        bids_match = re.search(r'# Bids:\s*(\d+)', text)
                        if bids_match:
                            bids_count = int(bids_match.group(1))

                        # Extract min bid
                        min_match = re.search(r'Min Bid:\s*\$?([\d,]+)', text)
                        if min_match:
                            min_bid = float(min_match.group(1).replace(',', ''))

                        # Extract final price (auction ended)
                        final_match = re.search(r'Final Price:\s*\$?([\d,]+)', text)
                        if final_match:
                            current_bid = float(final_match.group(1).replace(',', ''))
                            status = "Ended"

                        # Extract current bid (active auction)
                        current_match = re.search(r'Current Bid:\s*\$?([\d,]+)', text)
                        if current_match:
                            current_bid = float(current_match.group(1).replace(',', ''))

                # If no current bid, use min bid
                if current_bid is None and min_bid:
                    current_bid = min_bid

                # Extract grading info
                grading_info = self.extract_grading_info(title or "")

                # Extract category
                category = self.extract_category(title or "")

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
                    "end_time": None,  # Not available in listing
                    "status": status,
                    "item_url": item_url,
                    "raw_data": {
                        "lot_number": lot_number,
                        "min_bid": min_bid,
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

        # Look for pagination elements - Mile High uses page=N parameter
        page_links = soup.find_all('a', href=lambda x: x and 'page=' in str(x))
        max_page = 1
        for link in page_links:
            href = link.get('href', '')
            page_match = re.search(r'page=(\d+)', href)
            if page_match:
                page_num = int(page_match.group(1))
                max_page = max(max_page, page_num)
        pagination_info['total_pages'] = max_page

        # Count items on page
        items = soup.find_all('div', class_='lot')
        pagination_info['total_items'] = len(items)

        return pagination_info

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function with pagination support"""
        print("🔍 Fetching items from Mile High Card Company...")

        all_items = []

        try:
            # Fetch first page
            print("📡 Fetching catalog page (using Playwright)...")
            html = await self.fetch_page(self.catalog_url)

            # Get pagination info
            soup = BeautifulSoup(html, 'html.parser')
            pagination_info = self.get_pagination_info(soup)
            print(f"   Items on first page: {pagination_info['total_items']}")
            print(f"   Total pages available: {pagination_info['total_pages']}")

            # Limit pages to scrape
            pages_to_scrape = min(max_pages, pagination_info['total_pages'])
            print(f"   Will scrape {pages_to_scrape} pages (max_pages={max_pages})\n")

            # Parse items from each page
            for page_num in range(1, pages_to_scrape + 1):
                try:
                    print(f"📦 Page {page_num}/{pages_to_scrape}...")

                    if page_num == 1:
                        page_html = html
                    else:
                        page_url = f"{self.catalog_url}?page={page_num}"
                        page_html = await self.fetch_page(page_url)
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
        finally:
            await self._close_browser()

        # Create or update auction
        print("\n📦 Creating/updating auction record...")
        auction_external_id = "milehigh-current"

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
                title="Mile High Card Company",
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
                # Update existing item
                for key, value in item_data.items():
                    if key not in ['external_id', 'auction_house']:
                        setattr(existing_item, key, value)
                existing_item.updated_at = datetime.utcnow()
            else:
                # Create new item
                item = AuctionItem(
                    auction_id=auction.id,
                    auction_house=self.auction_house_name,
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
        """Check if Mile High Card Company website is reachable"""
        try:
            html = await self.fetch_page(self.catalog_url)
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.find_all('div', class_='lot')

            if items:
                return HealthCheckResult(
                    healthy=True,
                    message="Mile High Card Company is reachable",
                    details={"items_on_page": len(items)}
                )
            return HealthCheckResult(
                healthy=False,
                message="Mile High Card Company returned no items",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Mile High Card Company unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = MileHighScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
