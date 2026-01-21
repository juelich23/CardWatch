#!/usr/bin/env python3
"""
Greg Morris Cards Scraper
Fetches auction items from Greg Morris Cards using their API.
"""

import asyncio
import re
import httpx
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult
from app.utils.sport_detection import detect_sport_from_item


class GregMorrisScraper:
    def __init__(self):
        self.base_url = "https://gregmorriscards.com"
        self.api_url = f"{self.base_url}/auctions/getListings"
        self.auction_house_name = "gregmorris"

    def extract_grading_info(self, item: dict) -> dict:
        """Extract grading info from API response"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        grading_service = item.get('grading_service')
        if grading_service:
            company_map = {
                'BGS': 'Beckett',
                'BECKETT': 'Beckett',
                'BCCG': 'Beckett',
                'PSA': 'PSA',
                'SGC': 'SGC',
                'CGC': 'CGC'
            }
            result['grading_company'] = company_map.get(grading_service.upper(), grading_service)

        service_grade = item.get('service_grade')
        if service_grade:
            result['grade'] = str(service_grade)
        elif item.get('grade'):
            result['grade'] = item.get('grade')

        return result

    def extract_category(self, item: dict) -> str:
        """Extract category from item data"""
        name = (item.get('name') or '').upper()
        manufacturer = (item.get('manufacturer') or '').upper()

        if any(kw in name or kw in manufacturer for kw in ['BASEBALL', 'TOPPS', 'BOWMAN', 'DONRUSS']):
            return 'Baseball'
        if any(kw in name for kw in ['BASKETBALL', 'NBA', 'FLEER']):
            return 'Basketball'
        if any(kw in name for kw in ['FOOTBALL', 'NFL']):
            return 'Football'
        if any(kw in name for kw in ['HOCKEY', 'NHL']):
            return 'Hockey'
        if any(kw in name for kw in ['POKEMON', 'CHARIZARD']):
            return 'Pokemon'

        return 'Sports Cards'

    async def fetch_listings(self, page: int = 1) -> dict:
        """Fetch listings from the API"""
        params = {
            'page': page,
            'options[card_year][0]': 0,
            'options[card_price][0]': 0,
            'options[search]': '',
            'sort[sort_field]': 'end_time',
            'sort[sort_dir]': 'asc'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/auctions'
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(self.api_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

    def parse_items(self, data: dict) -> list:
        """Parse API response into normalized items"""
        normalized_items = []

        listings = data.get('listings', {})
        items = listings.get('data', [])

        for item in items:
            try:
                # Extract external ID
                external_id = str(item.get('item_id'))
                if not external_id:
                    continue

                # Build title from name and card info
                name = item.get('name', '')
                card_year = item.get('card_year')
                manufacturer = item.get('manufacturer', '')
                card_number = item.get('card_number')

                title_parts = []
                if card_year:
                    title_parts.append(str(card_year))
                if manufacturer:
                    title_parts.append(manufacturer)
                if name:
                    title_parts.append(name)
                if card_number:
                    title_parts.append(f"#{card_number}")

                title = ' '.join(title_parts) if title_parts else name

                if not title or len(title) < 3:
                    continue

                # Extract image URL (first from pipe-separated list)
                gallery_url = item.get('gallery_url', '')
                image_url = gallery_url.split('|')[0] if gallery_url else None

                # Extract price
                current_bid = item.get('current_price')
                if current_bid is not None:
                    current_bid = float(current_bid)

                # Parse end time
                end_time = None
                end_time_str = item.get('end_time')
                if end_time_str:
                    try:
                        end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            end_time = datetime.strptime(end_time_str, '%Y-%m-%d')
                        except ValueError:
                            pass

                # Extract grading info
                grading_info = self.extract_grading_info(item)

                # Extract category
                category = self.extract_category(item)

                # Detect sport from item content
                sport = detect_sport_from_item(title, None, category).value

                # Build item URL
                item_url = f"{self.base_url}/listing/{external_id}"

                normalized_item = {
                    "external_id": external_id,
                    "lot_number": external_id,
                    "cert_number": grading_info['cert_number'],
                    "sub_category": category,
                    "grading_company": grading_info['grading_company'],
                    "grade": grading_info['grade'],
                    "title": title[:500],
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
                        "card_year": card_year,
                        "manufacturer": manufacturer,
                        "card_number": card_number,
                    }
                }

                normalized_items.append(normalized_item)

            except Exception as e:
                print(f"   Warning: Error parsing item: {e}")
                continue

        return normalized_items

    async def scrape(self, db: AsyncSession, max_items: int = 1000, max_pages: int = 50) -> list:
        """Main scraping function"""
        print("Fetching items from Greg Morris Cards...")

        all_items = []

        try:
            # Fetch first page to get total
            print("   Fetching page 1...")
            data = await self.fetch_listings(page=1)
            listings = data.get('listings', {})
            total = listings.get('total', 0)
            last_page = listings.get('last_page', 1)
            print(f"   Total items available: {total}")
            print(f"   Total pages: {last_page}")

            items = self.parse_items(data)
            print(f"   Found {len(items)} items on page 1")
            all_items.extend(items)

            # Fetch remaining pages
            pages_to_fetch = min(last_page, max_pages)
            for page in range(2, pages_to_fetch + 1):
                if len(all_items) >= max_items:
                    break

                print(f"   Fetching page {page}/{pages_to_fetch}...")
                try:
                    data = await self.fetch_listings(page=page)
                    items = self.parse_items(data)
                    print(f"   Found {len(items)} items on page {page}")
                    all_items.extend(items)
                    await asyncio.sleep(0.5)  # Rate limiting
                except Exception as e:
                    print(f"   Warning: Error on page {page}: {e}")
                    continue

            if len(all_items) > max_items:
                all_items = all_items[:max_items]

            print(f"\n   Found {len(all_items)} total items")

        except Exception as e:
            print(f"   Error fetching listings: {e}")
            return []

        if not all_items:
            print("   No items found")
            return []

        # Create or update auction
        auction_external_id = "gregmorris-current"

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
                title="Greg Morris Cards",
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
        """Check if Greg Morris Cards API is reachable"""
        try:
            data = await self.fetch_listings(page=1)
            listings = data.get('listings', {})
            total = listings.get('total', 0)

            if total > 0:
                return HealthCheckResult(
                    healthy=True,
                    message="Greg Morris Cards is reachable",
                    details={"total_items": total}
                )
            return HealthCheckResult(
                healthy=False,
                message="Greg Morris Cards API returned no items",
                details={"response": data}
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Greg Morris Cards unreachable: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = GregMorrisScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\nScraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
