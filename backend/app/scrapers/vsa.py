#!/usr/bin/env python3
"""
VSA Auctions Scraper
Fetches auction items from VSA Auctions.
Uses Playwright for browser-based scraping (403 protection).
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


class VSAScraper:
    def __init__(self):
        self.base_url = "https://vsaauctions.com"
        self.auction_house_name = "vsa"
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

        # Try various item container selectors
        lots = soup.find_all('div', class_='lot') or \
               soup.find_all('div', class_='item') or \
               soup.find_all('div', class_='auction-item') or \
               soup.find_all('div', class_='lot-item')

        for lot_div in lots:
            try:
                # Extract title
                title_elem = lot_div.find(['h2', 'h3', 'h4', 'a', 'span'], class_=lambda x: x and any(
                    word in str(x).lower() for word in ['title', 'name', 'lot']
                ))
                if not title_elem:
                    title_elem = lot_div.find('a')

                title = title_elem.get_text().strip() if title_elem else None

                if not title or len(title) < 5:
                    continue

                # Extract URL
                link = lot_div.find('a', href=True)
                item_url = None
                if link:
                    href = link.get('href', '')
                    item_url = href if href.startswith('http') else f"{self.base_url}{href}"

                # Extract external ID
                external_id = None
                if item_url:
                    id_match = re.search(r'[/-](\d+)', item_url)
                    if id_match:
                        external_id = id_match.group(1)

                if not external_id:
                    continue

                # Extract lot number
                lot_number_elem = lot_div.find(string=re.compile(r'Lot\s*#?\s*\d+', re.I))
                lot_number = None
                if lot_number_elem:
                    lot_match = re.search(r'Lot\s*#?\s*(\d+)', lot_number_elem, re.I)
                    if lot_match:
                        lot_number = lot_match.group(1)

                # Extract image
                img = lot_div.find('img')
                image_url = None
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        image_url = src if src.startswith('http') else f"{self.base_url}{src}"

                # Extract bid info
                text = lot_div.get_text()
                current_bid = self.parse_price(re.search(r'Current\s*Bid[:\s]*\$?([\d,]+)', text, re.I).group(1)) if re.search(r'Current\s*Bid[:\s]*\$?([\d,]+)', text, re.I) else None
                starting_bid = self.parse_price(re.search(r'(?:Start|Min|Opening)\s*Bid[:\s]*\$?([\d,]+)', text, re.I).group(1)) if re.search(r'(?:Start|Min|Opening)\s*Bid[:\s]*\$?([\d,]+)', text, re.I) else None

                bids_match = re.search(r'(\d+)\s*Bids?', text, re.I)
                bids_count = int(bids_match.group(1)) if bids_match else 0

                # Skip ended items
                if 'ended' in text.lower() or 'sold' in text.lower() or 'closed' in text.lower():
                    continue

                if current_bid is None and starting_bid:
                    current_bid = starting_bid

                grading_info = self.extract_grading_info(title)
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
                    "starting_bid": starting_bid,
                    "bid_count": bids_count,
                    "end_time": None,
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {"lot_number": lot_number}
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   Warning: Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function"""
        print("Fetching items from VSA Auctions...")

        all_items = []

        try:
            # Try common catalog URLs
            catalog_urls = [
                f"{self.base_url}/auctions",
                f"{self.base_url}/catalog",
                f"{self.base_url}/lots",
                self.base_url,
            ]

            for url in catalog_urls:
                try:
                    print(f"   Trying: {url}")
                    html = await self.fetch_page(url)
                    items = self.parse_items(html)
                    if items:
                        print(f"   Found {len(items)} items at {url}")
                        all_items.extend(items)
                        break
                except Exception as e:
                    print(f"   Failed: {e}")
                    continue

            print(f"\n   Found {len(all_items)} total items")

        finally:
            await self._close_browser()

        if not all_items:
            print("   No items found - site may have no active auctions")
            return []

        # Create or update auction
        auction_external_id = "vsa-current"

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
                title="VSA Auctions",
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

        return all_items

    async def health_check(self) -> HealthCheckResult:
        """Check if VSA Auctions is reachable"""
        try:
            html = await self.fetch_page(self.base_url)
            if len(html) > 1000:
                return HealthCheckResult(
                    healthy=True,
                    message="VSA Auctions is reachable",
                    details={"html_length": len(html)}
                )
            return HealthCheckResult(
                healthy=False,
                message="VSA Auctions returned minimal content",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"VSA Auctions unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = VSAScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\nScraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
