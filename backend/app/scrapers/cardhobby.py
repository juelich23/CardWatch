import asyncio
import httpx
import os
import json
import re
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import select
from app.scrapers.base import BaseScraper, retry_async, HealthCheckResult
from app.models import Auction, AuctionItem
from app.utils.sport_detection import detect_sport_from_item


class CardHobbyScraper(BaseScraper):
    """
    Scraper for CardHobby marketplace (cardhobby.com)
    Focuses on auction listings over $100 USD
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        super().__init__(db)
        self.auction_house_name = "cardhobby"
        self.base_url = "https://gatewayapi.cardhobby.com"
        self.api_url = f"{self.base_url}/solr/NewCommodity/SearchCommodityPost"
        self.client = None

        # Auth token - can be set via environment variable
        self.auth_token = os.getenv("CARDHOBBY_AUTH_TOKEN", "")

    async def __aenter__(self):
        """Create HTTP client"""
        self.client = httpx.AsyncClient(
            headers=self._get_headers(),
            follow_redirects=True,
            timeout=30.0
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()

    def _get_headers(self) -> dict:
        """Get request headers with auth token"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://www.cardhobby.com',
            'Referer': 'https://www.cardhobby.com/',
            'Authorization': f'Bearer {self.auth_token}' if self.auth_token else '',
        }

    def _parse_price(self, price_str) -> float:
        """Parse price string, handling commas"""
        if not price_str:
            return 0.0
        try:
            return float(str(price_str).replace(',', ''))
        except (ValueError, TypeError):
            return 0.0

    async def health_check(self) -> HealthCheckResult:
        """Check if CardHobby API is accessible"""
        try:
            async with httpx.AsyncClient(headers=self._get_headers(), timeout=10.0) as client:
                response = await client.post(
                    self.api_url,
                    json={
                        "userId": "",
                        "pageIndex": 1,
                        "pageSize": 1,
                        "searchKey": "",
                        "searchJson": '[{"Key":"Status","Value":1},{"Key":"ByWay","Value":"2"}]',
                        "sort": "Price",
                        "sortType": "desc",
                        "lag": "en",
                        "device": "Web",
                        "version": 1,
                        "appname": "Card Hobby"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("result") == 1:
                        return HealthCheckResult(
                            healthy=True,
                            message="CardHobby API is accessible",
                            details={"total_auctions": data.get("data", {}).get("Total", 0)}
                        )

                return HealthCheckResult(
                    healthy=False,
                    message=f"CardHobby API returned status {response.status_code}",
                    details={"response": response.text[:500]}
                )

        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"CardHobby API error: {str(e)}"
            )

    async def scrape_active_auctions(self) -> List[Dict]:
        """Get active auctions - CardHobby doesn't have separate auctions, return placeholder"""
        return [{
            "auction_house": "cardhobby",
            "external_id": "current",
            "title": "CardHobby Current Auctions",
            "status": "active",
        }]

    @retry_async(max_retries=3, delay=2.0)
    async def _fetch_page(self, page: int, page_size: int = 100) -> dict:
        """Fetch a single page of auction items"""
        payload = {
            "userId": "",
            "pageIndex": page,
            "pageSize": page_size,
            "searchKey": "",
            # Status=1 (active), ByWay=2 (auctions)
            # Note: ByWay=1 is fixed-price, ByWay=2 is auctions
            "searchJson": '[{"Key":"Status","Value":1},{"Key":"ByWay","Value":"2"}]',
            # Sort by LowestPrice (current bid) descending to get high-value items first
            # Note: "Price" is starting price, "LowestPrice" is current bid
            "sort": "LowestPrice",
            "sortType": "desc",
            "lag": "en",
            "device": "Web",
            "version": 1,
            "appname": "Card Hobby"
        }

        response = await self.client.post(self.api_url, json=payload)
        response.raise_for_status()
        return response.json()

    async def scrape_auction_items(self, auction_id: str = None, max_items: int = 2000) -> List[Dict]:
        """
        Scrape auction items from CardHobby.
        Filters to items over $100 USD.
        Note: Auth token is optional for read-only operations.
        """
        print(f"\n🔍 Fetching auctions from CardHobby API...")

        all_items = []
        page = 1
        page_size = 100
        min_price = 100.0  # Filter to items over $100

        try:
            # First request to get total count
            data = await self._fetch_page(page, page_size)

            if data.get("result") != 1:
                print(f"   API error: {data.get('msg', 'Unknown error')}")
                return []

            total_available = data.get("data", {}).get("Total", 0)
            print(f"   Total auctions available: {total_available}")

            while len(all_items) < max_items:
                if page > 1:
                    data = await self._fetch_page(page, page_size)

                items = data.get("data", {}).get("PagedMarketItemList", [])

                if not items:
                    print(f"   No more items at page {page}")
                    break

                # Filter and transform items
                for item in items:
                    try:
                        # API field names are counterintuitive:
                        # - USD_Price = starting/initial price
                        # - USD_LowestPrice = current highest bid
                        current_bid = self._parse_price(item.get("USD_LowestPrice", 0))
                        starting_price = self._parse_price(item.get("USD_Price", 0))

                        # Skip items with current bid under $100
                        if current_bid < min_price:
                            continue

                        # Parse end time - CardHobby uses China Standard Time (UTC+8)
                        end_time_str = item.get("EffectiveDate", "")
                        try:
                            # Parse as naive datetime (in CST)
                            local_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                            # Convert from CST (UTC+8) to UTC
                            cst = timezone(timedelta(hours=8))
                            local_aware = local_time.replace(tzinfo=cst)
                            end_time = local_aware.astimezone(timezone.utc).replace(tzinfo=None)
                        except:
                            end_time = None

                        # Skip ended auctions
                        if end_time and end_time < datetime.utcnow():
                            continue

                        transformed = {
                            "external_id": str(item.get("ID")),
                            "title": item.get("Title", ""),
                            "image_url": item.get("TitImg", ""),
                            "current_bid": current_bid,
                            "starting_bid": starting_price,
                            "bid_count": item.get("PriceCount", 0),
                            "end_time": end_time,
                            "lot_number": item.get("Code", ""),
                            "status": "Live" if item.get("Status") == 1 else "Ended",
                            "item_url": f"https://www.cardhobby.com/#/carddetails/{item.get('ID')}",
                            "raw_data": {
                                "seller": item.get("SellRealName"),
                                "seller_id": item.get("SellMemberID"),
                                "sell_source": item.get("SellSource"),
                                "review_count": item.get("ReviewCount"),
                                "cny_price": item.get("Price"),
                            }
                        }

                        all_items.append(transformed)

                        if len(all_items) >= max_items:
                            break

                    except Exception as e:
                        print(f"   Error processing item: {e}")
                        continue

                print(f"   Page {page}: {len(items)} items, {len(all_items)} total (>= ${min_price})")

                # Check if we've gotten all high-value items (since sorted by current bid desc)
                # If last item in page is under threshold, we're done
                if items:
                    last_current_bid = self._parse_price(items[-1].get("USD_LowestPrice", 0))
                    if last_current_bid < min_price:
                        print(f"   Reached items under ${min_price}, stopping pagination")
                        break

                page += 1
                await asyncio.sleep(0.3)  # Rate limiting

        except Exception as e:
            print(f"   Error fetching from CardHobby: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n📦 Found {len(all_items)} items over ${min_price}")

        return all_items

    async def get_item_details(self, item_id: str) -> Optional[Dict]:
        """Get detailed information about a specific item"""
        # CardHobby may have a separate detail API - for now return None
        # The list API provides sufficient data
        return None

    async def scrape(self, db: AsyncSession, max_items: int = 2000) -> List[Dict]:
        """
        Main scraping entry point.
        """
        self.db = db

        async with self:
            items = await self.scrape_auction_items(max_items=max_items)

            if not items:
                print("   No items to save")
                return []

            # Create or get the CardHobby auction record
            print(f"\n📦 Creating/updating CardHobby auction record...")
            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == "cardhobby",
                    Auction.external_id == "cardhobby-current"
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                auction = Auction(
                    auction_house="cardhobby",
                    external_id="cardhobby-current",
                    title="CardHobby Current Auctions",
                    status="active",
                )
                db.add(auction)
                await db.flush()

            # Detect sports and enhance items
            print(f"\n🏷️ Detecting sports categories...")
            for item in items:
                sport = detect_sport_from_item(
                    title=item.get("title", ""),
                    category=item.get("category", ""),
                )
                item["sport"] = sport.value if hasattr(sport, 'value') else str(sport)
                item["category"] = "Trading Cards"
                item["auction_id"] = auction.id  # Link to auction record

            # Save to database
            print(f"\n💾 Saving {len(items)} items to database...")
            await self.save_to_database(items)

            return items
