#!/usr/bin/env python3
"""
Lelands Auction Scraper
Fetches auction items from Lelands by parsing HTML pages.
Uses Playwright for browser-based scraping (Lelands blocks regular HTTP requests).
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


class LelandsScraper:
    def __init__(self):
        self.base_url = "https://auction.lelands.com"
        self.gallery_url = f"{self.base_url}/Lots/Gallery"
        self.auction_house_name = "lelands"
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
        # Examples: "PSA 10", "BGS 9.5", "SGC 9", "BCCG 9", "PSA EX-MT+ 6.5"
        grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC|BCCG)\s+(?:[\w\-\+]+\s+)?(\d+(?:\.\d+)?)\b'
        match = re.search(grading_pattern, title, re.IGNORECASE)

        if match:
            company = match.group(1)
            grade = match.group(2)

            # Normalize grading company names
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
        categories = {
            'Basketball': ['Basketball', 'NBA', 'Kobe', 'Jordan', 'LeBron', 'Curry'],
            'Football': ['Football', 'NFL', 'Mahomes', 'Brady', 'Playoff Contenders'],
            'Baseball': ['Baseball', 'MLB', 'Topps', 'Bowman', 'Trout', 'Ohtani', 'Ruth', 'Mantle'],
            'Hockey': ['Hockey', 'NHL', 'Gretzky'],
            'Soccer': ['Soccer', 'MLS', 'Messi', 'Ronaldo'],
            'Pokemon': ['Pokemon', 'Pikachu', 'Charizard'],
            'Magic The Gathering': ['Magic', 'MTG'],
            'Memorabilia': ['Jersey', 'Autograph', 'Signed', 'Game-Used', 'Photo']
        }

        title_upper = title.upper()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.upper() in title_upper:
                    return category

        return None

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string like '$20,000' or 'SOLD FOR $163,593'"""
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
        """Fetch a page using Playwright (Lelands blocks regular HTTP requests)"""
        await self._ensure_browser()

        context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)  # Wait for JS to render
            html = await page.content()
            return html
        finally:
            await page.close()
            await context.close()

    def get_pagination_info(self, soup: BeautifulSoup) -> dict:
        """Extract pagination information"""
        # Look for pagination links or "showing X of Y" text
        pagination_info = {
            'current_page': 1,
            'total_pages': 1,
            'total_items': 0
        }

        # Look for pagination elements
        pagination = soup.find('ul', class_='pagination')
        if pagination:
            page_links = pagination.find_all('a', href=True)
            max_page = 1
            for link in page_links:
                href = link.get('href', '')
                page_match = re.search(r'[?&]page=(\d+)', href)
                if page_match:
                    page_num = int(page_match.group(1))
                    max_page = max(max_page, page_num)
            pagination_info['total_pages'] = max_page

        # Count items on page
        items = soup.find_all('div', class_='item')
        pagination_info['total_items'] = len(items)

        return pagination_info

    def parse_items(self, html: str) -> list:
        """Parse auction items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all item containers
        items = soup.find_all('div', class_='item')
        normalized_items = []

        for item_div in items:
            try:
                # Extract lot number from h5.boxed
                lot_elem = item_div.find('h5', class_='boxed')
                lot_number = lot_elem.get_text().strip() if lot_elem else None

                # Extract title and URL from description link
                desc_link = item_div.select_one('p.description a')
                title = desc_link.get_text().strip() if desc_link else None
                item_url = desc_link.get('href') if desc_link else None

                # Extract item ID from URL
                external_id = None
                if item_url:
                    id_match = re.search(r'itemid=(\d+)', item_url)
                    if id_match:
                        external_id = id_match.group(1)

                # Extract image URL
                img_elem = item_div.select_one('div.item-image img')
                image_url = img_elem.get('src') if img_elem else None

                # Extract bid info from the middle paragraph
                details_div = item_div.find('div', class_='item-details')
                bids_count = None
                opening_bid = None
                status = None

                if details_div:
                    # Find all paragraphs in details
                    paragraphs = details_div.find_all('p')
                    for p in paragraphs:
                        text = p.get_text()
                        # Extract bids count
                        bids_match = re.search(r'Bids:\s*(\d+)', text)
                        if bids_match:
                            bids_count = int(bids_match.group(1))

                        # Extract opening bid
                        opening_match = re.search(r'Opening Bid:\s*\$?([\d,]+)', text)
                        if opening_match:
                            opening_bid = float(opening_match.group(1).replace(',', ''))

                        # Extract status
                        status_match = re.search(r'Status:\s*(\w+)', text)
                        if status_match:
                            status = status_match.group(1)

                # Extract current/final price from item-price div
                price_elem = item_div.select_one('div.item-price a')
                current_bid = None
                if price_elem:
                    price_text = price_elem.get_text().strip()
                    current_bid = self.parse_price(price_text)

                # If status is "Sold", mark as ended
                is_active = status and status.lower() not in ['sold', 'closed', 'ended']

                # Skip ended auctions - only keep active ones
                if not is_active:
                    continue

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
                    "starting_bid": opening_bid,
                    "bid_count": bids_count if bids_count is not None else 0,
                    "end_time": None,  # Not available in gallery view
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {
                        "lot_number": lot_number,
                        "original_status": status,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function with pagination support"""
        print("🔍 Fetching items from Lelands Auction...")

        all_items = []

        try:
            # Fetch first page
            print("📡 Fetching first page (using Playwright)...")
            html = await self.fetch_page(self.gallery_url)

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
                        page_url = f"{self.gallery_url}?page={page_num}"
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
        auction_external_id = "lelands-current"

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
                title="Lelands Auction",
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
        """Check if Lelands website is reachable (using Playwright)"""
        try:
            html = await self.fetch_page(self.gallery_url)
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.find_all('div', class_='item')

            if items:
                return HealthCheckResult(
                    healthy=True,
                    message="Lelands Auction is reachable",
                    details={"items_on_page": len(items)}
                )
            return HealthCheckResult(
                healthy=False,
                message="Lelands returned no items",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Lelands unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    # Initialize database
    await init_db()

    scraper = LelandsScraper()

    # Get database session
    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
