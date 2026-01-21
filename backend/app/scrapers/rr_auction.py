#!/usr/bin/env python3
"""
RR Auction Scraper
Fetches items from RR Auction (historical items and autographs).
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


class RRAuctionScraper:
    def __init__(self):
        self.base_url = "https://www.rrauction.com"
        self.auctions_url = f"{self.base_url}/auctions/auction-calendar"
        self.auction_house_name = "rr_auction"
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
        """Extract category from title"""
        title_upper = title.upper()

        if any(kw in title_upper for kw in ['SPACE', 'NASA', 'ASTRONAUT', 'APOLLO']):
            return 'Space'
        if any(kw in title_upper for kw in ['MUSIC', 'BEATLES', 'ELVIS', 'GUITAR']):
            return 'Music'
        if any(kw in title_upper for kw in ['HISTORICAL', 'PRESIDENT', 'CIVIL WAR']):
            return 'Historical'
        if any(kw in title_upper for kw in ['BASEBALL', 'BABE RUTH', 'MLB']):
            return 'Baseball'
        if any(kw in title_upper for kw in ['BASKETBALL', 'NBA', 'JORDAN']):
            return 'Basketball'
        if any(kw in title_upper for kw in ['FOOTBALL', 'NFL']):
            return 'Football'
        if any(kw in title_upper for kw in ['SIGNED', 'AUTOGRAPH', 'DOCUMENT']):
            return 'Autographs'

        return 'Autographs'  # Default for RR Auction

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string like 'Now At: $4,965'"""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            return float(match.group(1).replace(',', ''))
        return None

    def parse_bid_count(self, text: str) -> Optional[int]:
        """Parse bid count from text like '(16 bids)'"""
        if not text:
            return None
        match = re.search(r'\((\d+)\s*bids?\)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
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
            await asyncio.sleep(3)
            html = await page.content()
            return html
        finally:
            await page.close()
            await context.close()

    async def get_active_auctions(self) -> List[str]:
        """Get list of active auction URLs"""
        html = await self.fetch_page(self.auctions_url)
        soup = BeautifulSoup(html, 'html.parser')

        auction_urls = []
        links = soup.find_all('a', href=lambda x: x and '/auctions/details/' in x)

        seen = set()
        for link in links:
            href = link.get('href')
            if href and href not in seen:
                full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                # Remove query params for dedup
                base_url = full_url.split('?')[0]
                if base_url not in seen:
                    seen.add(base_url)
                    auction_urls.append(base_url)

        return auction_urls[:15]  # Limit to 15 auctions

    def parse_items(self, html: str) -> list:
        """Parse items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Find all auction item containers
        items = soup.find_all('div', class_=lambda x: x and 'auction-item' in x and 'auction-item--skin' in str(x))
        normalized_items = []

        for item_div in items:
            try:
                # Get item ID from container ID
                item_id = item_div.get('id', '')
                external_id = item_id.replace('-gallery', '') if item_id else None

                # Find title link
                title_link = item_div.select_one('a.auction-item__title')
                title_elem = item_div.select_one('h2.title')
                title = title_elem.get_text().strip() if title_elem else None

                # Get URL from title link
                item_url = None
                if title_link:
                    href = title_link.get('href')
                    item_url = f"{self.base_url}{href}" if href and href.startswith('/') else href

                # Extract external ID from URL if not found
                if not external_id and item_url:
                    id_match = re.search(r'/lot-detail/(\d+)-', item_url)
                    if id_match:
                        external_id = id_match.group(1)

                # Extract lot number from title
                lot_number = None
                if title:
                    lot_match = re.match(r'^(\d+)\.\s*', title)
                    if lot_match:
                        lot_number = lot_match.group(1)
                        # Remove lot number from title
                        title = title[len(lot_match.group(0)):].strip()

                # Find image
                img = item_div.select_one('img.zoom-hover, img.img-fluid')
                image_url = img.get('src') if img else None

                # Find price and bid count
                value_elem = item_div.select_one('p.value')
                current_bid = None
                bid_count = None
                if value_elem:
                    value_text = value_elem.get_text()
                    current_bid = self.parse_price(value_text)
                    bid_count = self.parse_bid_count(value_text)

                # Find estimate
                estimate_elem = item_div.select_one('p.gallery-estimate')
                starting_bid = None
                if estimate_elem:
                    estimate_text = estimate_elem.get_text()
                    starting_bid = self.parse_price(estimate_text)

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
                    "starting_bid": starting_bid,
                    "bid_count": bid_count if bid_count is not None else 0,
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

    async def scrape(self, db: AsyncSession, max_items: int = 1000) -> list:
        """Main scraping function"""
        print("🔍 Fetching items from RR Auction...")

        all_items = []

        try:
            # Get active auctions
            print("📡 Finding active auctions...")
            auction_urls = await self.get_active_auctions()
            print(f"   Found {len(auction_urls)} auctions")

            # Scrape each auction with pagination
            for i, auction_url in enumerate(auction_urls):
                if len(all_items) >= max_items:
                    break

                print(f"\n📦 Auction {i + 1}/{len(auction_urls)}: {auction_url[:60]}...")

                try:
                    # Fetch first page of auction
                    html = await self.fetch_page(auction_url)
                    items = self.parse_items(html)
                    print(f"   Page 1: Found {len(items)} items")
                    all_items.extend(items)

                    # Check for pagination within auction
                    soup = BeautifulSoup(html, 'html.parser')
                    page_links = soup.find_all('a', href=lambda x: x and 'page=' in str(x))
                    max_page = 1
                    for link in page_links:
                        href = link.get('href', '')
                        page_match = re.search(r'page=(\d+)', href)
                        if page_match:
                            max_page = max(max_page, int(page_match.group(1)))

                    # Scrape additional pages if available (limit to 10 pages per auction)
                    pages_to_scrape = min(10, max_page)
                    for page_num in range(2, pages_to_scrape + 1):
                        if len(all_items) >= max_items:
                            break
                        try:
                            page_url = f"{auction_url}?page={page_num}"
                            page_html = await self.fetch_page(page_url)
                            page_items = self.parse_items(page_html)
                            print(f"   Page {page_num}: Found {len(page_items)} items")
                            all_items.extend(page_items)
                            await asyncio.sleep(1)
                        except Exception as e:
                            print(f"   ⚠️ Error fetching page {page_num}: {e}")
                            break

                    await asyncio.sleep(1)  # Rate limiting between auctions
                except Exception as e:
                    print(f"   ⚠️ Error fetching auction: {e}")

            if len(all_items) > max_items:
                all_items = all_items[:max_items]

            normalized_items = all_items
            print(f"\n✅ Found {len(normalized_items)} total items")
        finally:
            await self._close_browser()

        # Create or update auction
        print("\n📦 Creating/updating auction record...")
        auction_external_id = "rr-current"

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
                title="RR Auction",
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
        """Check if RR Auction website is reachable"""
        try:
            html = await self.fetch_page(self.auctions_url)
            soup = BeautifulSoup(html, 'html.parser')

            # Check for auction links
            links = soup.find_all('a', href=lambda x: x and '/auctions/details/' in x)

            if links:
                return HealthCheckResult(
                    healthy=True,
                    message="RR Auction is reachable",
                    details={"auction_links_found": len(set([l.get('href') for l in links]))}
                )
            return HealthCheckResult(
                healthy=False,
                message="RR Auction returned no auctions",
                details={"html_length": len(html)}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"RR Auction unreachable: {str(e)}",
                details={"error": str(e)}
            )
        finally:
            await self._close_browser()


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = RRAuctionScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=500)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
