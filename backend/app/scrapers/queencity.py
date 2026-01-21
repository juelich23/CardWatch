#!/usr/bin/env python3
"""
Queen City Cards Scraper
Fetches auction items from Queen City Cards via AuctionNinja platform.
Uses Playwright to navigate auction pages and parse lot data.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, List
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult
from app.utils.sport_detection import detect_sport_from_item


class QueenCityScraper:
    def __init__(self):
        self.base_url = "https://www.auctionninja.com"
        self.seller_url = f"{self.base_url}/queen-city-cards/"
        self.auction_house_name = "queencity"
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

        if any(kw in title_upper for kw in ['BASEBALL', 'MLB', 'TOPPS', 'BOWMAN', 'DONRUSS']):
            return 'Baseball'
        if any(kw in title_upper for kw in ['BASKETBALL', 'NBA', 'PANINI']):
            return 'Basketball'
        if any(kw in title_upper for kw in ['FOOTBALL', 'NFL']):
            return 'Football'
        if any(kw in title_upper for kw in ['HOCKEY', 'NHL']):
            return 'Hockey'
        if any(kw in title_upper for kw in ['POKEMON', 'CHARIZARD']):
            return 'Pokemon'

        return 'Sports Cards'

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string"""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            return float(match.group(1).replace(',', ''))
        return None

    def parse_time_remaining(self, text: str) -> Optional[datetime]:
        """Parse time remaining into end datetime"""
        if not text:
            return None

        days = hours = minutes = 0

        day_match = re.search(r'(\d+)\s*days?', text, re.IGNORECASE)
        hour_match = re.search(r'(\d+)\s*hours?', text, re.IGNORECASE)
        min_match = re.search(r'(\d+)\s*min', text, re.IGNORECASE)

        if day_match:
            days = int(day_match.group(1))
        if hour_match:
            hours = int(hour_match.group(1))
        if min_match:
            minutes = int(min_match.group(1))

        if days or hours or minutes:
            return datetime.utcnow() + timedelta(days=days, hours=hours, minutes=minutes)
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
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Scroll to load more content
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(0.5)

            html = await page.content()
            return html
        finally:
            await page.close()
            await context.close()

    async def get_auction_urls(self, html: str) -> List[str]:
        """Extract auction detail URLs from seller page"""
        soup = BeautifulSoup(html, 'html.parser')
        auction_urls = []

        # Find links to auction detail pages
        links = soup.find_all('a', href=lambda x: x and '/sales/details/' in str(x))

        seen = set()
        for link in links:
            href = link.get('href', '')
            # Remove query params
            clean_url = href.split('?')[0]
            if clean_url and clean_url not in seen:
                seen.add(clean_url)
                auction_urls.append(clean_url)

        return auction_urls

    def parse_lots(self, html: str, auction_url: str) -> list:
        """Parse lot items from auction detail page"""
        soup = BeautifulSoup(html, 'html.parser')
        normalized_items = []

        # Find lot containers
        lot_boxes = soup.find_all(class_='search-catalog-item-box')

        for box in lot_boxes:
            try:
                # Get lot number
                lot_elem = box.find(class_='lot-number')
                lot_text = lot_elem.get_text().strip() if lot_elem else ''
                lot_match = re.search(r'#?\s*(\d+)', lot_text)
                lot_number = lot_match.group(1) if lot_match else None

                # Get title
                title_elem = box.find(class_='hot-items-title')
                title = title_elem.get_text().strip() if title_elem else None

                if not title or len(title) < 5:
                    continue

                # Generate external ID from auction URL and lot number
                auction_id_match = re.search(r'-(\d+)\.html', auction_url)
                auction_id = auction_id_match.group(1) if auction_id_match else 'unknown'
                external_id = f"{auction_id}-{lot_number}" if lot_number else f"{auction_id}-{hash(title)}"

                # Get price
                box_text = box.get_text()
                current_bid = None
                price_match = re.search(r'Current\s*Bid\s*\$?([\d,]+(?:\.\d{2})?)', box_text, re.I)
                if price_match:
                    current_bid = float(price_match.group(1).replace(',', ''))
                else:
                    # Try just finding any price
                    price_match = re.search(r'\$([\d,]+(?:\.\d{2})?)', box_text)
                    if price_match:
                        current_bid = float(price_match.group(1).replace(',', ''))

                # Get image
                img = box.find('img')
                image_url = None
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src and not src.endswith('box-img.png'):  # Skip placeholder
                        image_url = src if src.startswith('http') else f"{self.base_url}{src}"

                # Parse time remaining
                end_time = None
                time_match = re.search(r'(\d+)\s*days?\s*(\d+)\s*hours?', box_text, re.I)
                if time_match:
                    days = int(time_match.group(1))
                    hours = int(time_match.group(2))
                    end_time = datetime.utcnow() + timedelta(days=days, hours=hours)

                # Get bid count
                bid_count = 0
                bids_match = re.search(r'(\d+)\s*bids?', box_text, re.I)
                if bids_match:
                    bid_count = int(bids_match.group(1))

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
                    "starting_bid": None,
                    "bid_count": bid_count,
                    "end_time": end_time,
                    "status": "Live",
                    "item_url": auction_url,
                    "raw_data": {"auction_url": auction_url}
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   Warning: Error parsing lot: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_auctions: int = 10) -> list:
        """Main scraping function"""
        print("Fetching items from Queen City Cards (AuctionNinja)...")

        all_items = []

        try:
            # Fetch seller page to get auction URLs
            print("   Fetching seller page...")
            seller_html = await self.fetch_page(self.seller_url)
            auction_urls = await self.get_auction_urls(seller_html)
            print(f"   Found {len(auction_urls)} auctions")

            # Scrape each auction
            for i, auction_url in enumerate(auction_urls[:max_auctions]):
                if len(all_items) >= max_items:
                    break

                print(f"   Auction {i+1}/{min(len(auction_urls), max_auctions)}: {auction_url[-60:]}")
                try:
                    auction_html = await self.fetch_page(auction_url)
                    lots = self.parse_lots(auction_html, auction_url)
                    print(f"      Found {len(lots)} lots")
                    all_items.extend(lots)
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"      Error: {e}")
                    continue

            if len(all_items) > max_items:
                all_items = all_items[:max_items]

            print(f"\n   Found {len(all_items)} total items")

        finally:
            await self._close_browser()

        if not all_items:
            print("   No items found - auctions may be scheduled for future dates")
            return []

        # Create or update auction
        auction_external_id = "queencity-current"

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
                title="Queen City Cards",
                status="active"
            )
            db.add(auction)
            await db.flush()

        # Save items to database
        for item_data in all_items:
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
        print(f"   Saved {len(all_items)} items to database")

        graded_items = [item for item in all_items if item.get('grading_company')]
        print(f"   Items with grading data: {len(graded_items)}")

        return all_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Queen City Cards is reachable"""
        try:
            html = await self.fetch_page(self.seller_url)
            if len(html) > 1000:
                return HealthCheckResult(
                    healthy=True,
                    message="Queen City Cards is reachable",
                    details={"html_length": len(html)}
                )
            return HealthCheckResult(
                healthy=False,
                message="Queen City Cards returned empty page",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Queen City Cards unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = QueenCityScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=500, max_auctions=5)

        print(f"\nScraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
