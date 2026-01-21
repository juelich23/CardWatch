#!/usr/bin/env python3
"""
Clean Sweep Auctions Scraper
Fetches items from Clean Sweep Auctions marketplace.
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


class CleanSweepScraper:
    def __init__(self):
        self.base_url = "https://marketplace.cleansweepauctions.com"
        self.auction_house_name = "cleansweep"
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

        return 'Baseball'  # Default for Clean Sweep

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string like 'Buy it for $21'"""
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
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            html = await page.content()
            return html
        finally:
            await page.close()
            await context.close()

    def parse_items(self, html: str) -> list:
        """Parse items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all product containers
        products = soup.find_all('div', class_='single-products')
        normalized_items = []

        for product in products:
            try:
                # Find title link
                title_link = product.select_one('h6 a')
                title = title_link.get_text().strip() if title_link else None
                item_url = title_link.get('href') if title_link else None

                # Extract external ID from URL
                external_id = None
                if item_url:
                    id_match = re.search(r'/item-0*(\d+)/?', item_url)
                    if id_match:
                        external_id = id_match.group(1)

                # Find image
                img = product.select_one('img')
                image_url = img.get('src') if img else None

                # Find price
                price_elem = product.find('p')
                current_bid = None
                if price_elem:
                    price_text = price_elem.get_text()
                    current_bid = self.parse_price(price_text)

                # Extract grading info
                grading_info = self.extract_grading_info(title or "")

                # Extract category
                category = self.extract_category(title or "")

                # Detect sport from item content
                sport = detect_sport_from_item(title, None, category).value

                normalized_item = {
                    "external_id": external_id,
                    "lot_number": external_id,  # Use item ID as lot number
                    "cert_number": grading_info['cert_number'],
                    "sub_category": category,
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500] if title else "",
                    "description": None,
                    "category": category,
                    "sport": sport,
                    "image_url": image_url,
                    "current_bid": current_bid,  # This is Buy Now price
                    "starting_bid": current_bid,
                    "bid_count": 0,  # Marketplace has no bids
                    "end_time": None,
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {
                        "buy_now_price": current_bid,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function with pagination support"""
        print("🔍 Fetching items from Clean Sweep Auctions...")

        all_items = []

        try:
            # Fetch first page
            print("📡 Fetching marketplace page...")
            html = await self.fetch_page(self.base_url)

            items = self.parse_items(html)
            print(f"   Found {len(items)} items on page")
            all_items.extend(items)

            # Check for pagination and fetch more pages if needed
            soup = BeautifulSoup(html, 'html.parser')
            page_links = soup.find_all('a', href=lambda x: x and 'page=' in str(x))

            # Get max page number
            max_page = 1
            for link in page_links:
                href = link.get('href', '')
                page_match = re.search(r'page=(\d+)', href)
                if page_match:
                    max_page = max(max_page, int(page_match.group(1)))

            pages_to_scrape = min(max_pages, max_page)
            print(f"   Total pages available: {max_page}")
            print(f"   Will scrape {pages_to_scrape} pages")

            # Fetch additional pages
            for page_num in range(2, pages_to_scrape + 1):
                if len(all_items) >= max_items:
                    break

                try:
                    print(f"📦 Page {page_num}/{pages_to_scrape}...")
                    page_url = f"{self.base_url}?page={page_num}"
                    page_html = await self.fetch_page(page_url)
                    page_items = self.parse_items(page_html)
                    print(f"   Found {len(page_items)} items")
                    all_items.extend(page_items)
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    print(f"   ⚠️ Error fetching page {page_num}: {e}")

            if len(all_items) > max_items:
                all_items = all_items[:max_items]

            normalized_items = all_items
            print(f"\n✅ Found {len(normalized_items)} total items")
        finally:
            await self._close_browser()

        # Create or update auction
        print("\n📦 Creating/updating auction record...")
        auction_external_id = "cleansweep-marketplace"

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
                title="Clean Sweep Auctions Marketplace",
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
        """Check if Clean Sweep website is reachable"""
        try:
            html = await self.fetch_page(self.base_url)
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.find_all('div', class_='single-products')

            if items:
                return HealthCheckResult(
                    healthy=True,
                    message="Clean Sweep Auctions is reachable",
                    details={"items_on_page": len(items)}
                )
            return HealthCheckResult(
                healthy=False,
                message="Clean Sweep returned no items",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Clean Sweep unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = CleanSweepScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
