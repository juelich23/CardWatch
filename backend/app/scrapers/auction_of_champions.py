#!/usr/bin/env python3
"""
Auction of Champions Scraper
Fetches auction items from Auction of Champions.
Uses httpx for HTTP requests.
"""

import asyncio
import httpx
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult
from app.utils.sport_detection import detect_sport_from_item


class AuctionOfChampionsScraper:
    def __init__(self):
        self.base_url = "https://auctionofchampions.com"
        self.search_url = f"{self.base_url}/lot/search"
        self.auction_house_name = "auction_of_champions"

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

    def extract_category(self, title: str, category_tag: str = None) -> Optional[str]:
        """Extract sport/category from title"""
        title_upper = title.upper()

        if any(kw in title_upper for kw in ['BASEBALL', 'MLB', 'TOPPS', 'BOWMAN']):
            return 'Baseball'
        if any(kw in title_upper for kw in ['BASKETBALL', 'NBA', 'JORDAN', 'LEBRON']):
            return 'Basketball'
        if any(kw in title_upper for kw in ['FOOTBALL', 'NFL', 'MAHOMES', 'BRADY']):
            return 'Football'
        if any(kw in title_upper for kw in ['HOCKEY', 'NHL', 'GRETZKY']):
            return 'Hockey'
        if any(kw in title_upper for kw in ['SOCCER', 'FIFA', 'MESSI', 'RONALDO']):
            return 'Soccer'
        if any(kw in title_upper for kw in ['POKEMON', 'CHARIZARD', 'PIKACHU']):
            return 'Pokemon'

        return 'Sports Cards'

    def parse_price(self, text: str) -> Optional[float]:
        """Parse a price string like '$1,234.56'"""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', text)
        if match:
            return float(match.group(1).replace(',', ''))
        return None

    def parse_time_remaining(self, text: str) -> Optional[datetime]:
        """Parse time remaining like '3d 20h 41m' into end datetime"""
        if not text:
            return None

        days = hours = minutes = 0

        day_match = re.search(r'(\d+)d', text)
        hour_match = re.search(r'(\d+)h', text)
        min_match = re.search(r'(\d+)m', text)

        if day_match:
            days = int(day_match.group(1))
        if hour_match:
            hours = int(hour_match.group(1))
        if min_match:
            minutes = int(min_match.group(1))

        if days or hours or minutes:
            return datetime.utcnow() + timedelta(days=days, hours=hours, minutes=minutes)
        return None

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
        """Parse auction items from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        normalized_items = []

        # Find all lot links - they follow pattern /lot/[id]-[slug]
        lot_links = soup.find_all('a', href=lambda x: x and re.search(r'/lot/\d+-', str(x)))

        seen_ids = set()

        for link in lot_links:
            try:
                href = link.get('href', '')

                # Extract lot ID and title from URL
                lot_match = re.search(r'/lot/(\d+)-(.+)', href)
                if not lot_match:
                    continue

                lot_id = lot_match.group(1)
                slug = lot_match.group(2)

                # Skip duplicates
                if lot_id in seen_ids:
                    continue
                seen_ids.add(lot_id)

                # Extract title from slug (convert dashes to spaces)
                title = slug.replace('-', ' ').strip()
                if not title or len(title) < 5:
                    continue

                # Find the container (parent elements) - go up to find bid/time info
                container = link
                for _ in range(6):
                    parent = container.parent
                    if parent:
                        container = parent
                        text = container.get_text()
                        if 'Bid:' in text or '$' in text:
                            break

                # Get full URL
                item_url = f"{self.base_url}{href}" if href.startswith('/') else href

                # Find image in container
                img = container.find('img')
                image_url = None
                if img:
                    image_url = img.get('src') or img.get('data-src')

                # Find bid amount
                container_text = container.get_text()
                current_bid = None
                bid_match = re.search(r'Bid:\s*\$?([\d,]+(?:\.\d{2})?)', container_text)
                if bid_match:
                    current_bid = float(bid_match.group(1).replace(',', ''))

                # Find time remaining
                end_time = None
                time_match = re.search(r'Time:\s*([\d]+[dhm]\s*[\d]*[dhm]?\s*[\d]*[dhm]?)', container_text)
                if time_match:
                    end_time = self.parse_time_remaining(time_match.group(1))

                # Find category tag
                category_tag = None
                for tag in ['card', 'mvp', 'all-star', 'mystery', 'daily']:
                    if tag in container_text.lower():
                        category_tag = tag
                        break

                # Extract grading info
                grading_info = self.extract_grading_info(title)

                # Extract category
                category = self.extract_category(title, category_tag)

                # Detect sport from item content
                sport = detect_sport_from_item(title, None, category).value

                normalized_item = {
                    "external_id": lot_id,
                    "lot_number": lot_id,
                    "cert_number": grading_info['cert_number'],
                    "sub_category": category_tag,
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500] if title else "",
                    "description": None,
                    "category": category,
                    "sport": sport,
                    "image_url": image_url,
                    "current_bid": current_bid,
                    "starting_bid": None,
                    "bid_count": 0,
                    "end_time": end_time,
                    "status": "Live",
                    "item_url": item_url,
                    "raw_data": {
                        "category_tag": category_tag,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   ⚠️ Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 2000) -> list:
        """Main scraping function"""
        print("🔍 Fetching items from Auction of Champions...")

        all_items = []

        async with httpx.AsyncClient() as client:
            # Fetch search page (shows all lots)
            print("📡 Fetching lot search page...")
            try:
                html = await self.fetch_page(client, self.search_url)
                items = self.parse_items(html)
                print(f"   Found {len(items)} items")
                all_items.extend(items)
            except Exception as e:
                print(f"   ⚠️ Error fetching search page: {e}")

            # Also try category pages if we need more
            if len(all_items) < 100:
                categories = ['daily', 'card', 'mvp', 'all-star', 'mystery']
                for category in categories:
                    if len(all_items) >= max_items:
                        break
                    try:
                        print(f"📦 Fetching {category} category...")
                        cat_url = f"{self.base_url}/auction/{category}"
                        html = await self.fetch_page(client, cat_url)
                        items = self.parse_items(html)
                        # Add only new items
                        existing_ids = {item['external_id'] for item in all_items}
                        new_items = [i for i in items if i['external_id'] not in existing_ids]
                        print(f"   Found {len(new_items)} new items")
                        all_items.extend(new_items)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"   ⚠️ Error fetching {category}: {e}")

            if len(all_items) > max_items:
                all_items = all_items[:max_items]

            normalized_items = all_items
            print(f"\n✅ Found {len(normalized_items)} total items")

        # Create or update auction
        print("\n📦 Creating/updating auction record...")
        auction_external_id = "aoc-current"

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
                title="Auction of Champions",
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
        """Check if Auction of Champions is reachable"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.base_url,
                    headers={'User-Agent': 'Mozilla/5.0'},
                    follow_redirects=True
                )
                if response.status_code == 200:
                    return HealthCheckResult(
                        healthy=True,
                        message="Auction of Champions is reachable",
                        details={"status_code": response.status_code}
                    )
                return HealthCheckResult(
                    healthy=False,
                    message=f"Auction of Champions returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Auction of Champions unreachable: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = AuctionOfChampionsScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=2000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
