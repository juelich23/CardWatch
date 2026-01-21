#!/usr/bin/env python3
"""
eBay Auction Scraper
Fetches auction listings from eBay using the Browse API.
Focuses on sports cards and collectibles categories.

Requires eBay Developer credentials:
- EBAY_CLIENT_ID: Your eBay app client ID
- EBAY_CLIENT_SECRET: Your eBay app client secret

Get credentials at: https://developer.ebay.com/
"""

import asyncio
import base64
import httpx
import os
import re
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult, retry_async
from app.utils.sport_detection import detect_sport_from_item


class EbayScraper:
    def __init__(self, sandbox: bool = None):
        self.client_id = os.getenv("EBAY_CLIENT_ID", "")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "")

        # Auto-detect sandbox mode from environment or client_id
        if sandbox is None:
            sandbox = os.getenv("EBAY_SANDBOX", "").lower() in ("true", "1", "yes")
            # Also detect if client_id contains SBX (sandbox indicator)
            if not sandbox and "SBX" in self.client_id.upper():
                sandbox = True

        self.sandbox = sandbox

        # eBay API endpoints (Sandbox vs Production)
        if self.sandbox:
            self.auth_url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
            self.browse_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
            print("   [eBay Sandbox Mode]")
        else:
            self.auth_url = "https://api.ebay.com/identity/v1/oauth2/token"
            self.browse_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

        # Access token (cached)
        self._access_token = None
        self._token_expiry = None

        # Sports cards and collectibles category IDs
        # 212 = Sports Trading Cards
        # 213 = Non-Sport Trading Cards
        # 64482 = Sports Memorabilia
        self.category_ids = ["212", "213", "64482"]

    async def get_access_token(self, client: httpx.AsyncClient) -> str:
        """Get OAuth access token using client credentials flow."""
        if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "eBay API credentials not configured. "
                "Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET environment variables."
            )

        # Base64 encode credentials
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }

        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }

        response = await client.post(self.auth_url, headers=headers, data=data, timeout=30.0)
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data["access_token"]

        # Set expiry (usually 2 hours, subtract 5 min for safety)
        expires_in = token_data.get("expires_in", 7200) - 300
        from datetime import timedelta
        self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

        print(f"   Got eBay access token (expires in {expires_in}s)")
        return self._access_token

    def extract_grading_info(self, title: str, condition_descriptors: List[Dict] = None) -> dict:
        """Extract grading company, grade, and cert number from title and condition descriptors."""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        # Check condition descriptors first (eBay's structured grading data)
        if condition_descriptors:
            for desc in condition_descriptors:
                name = desc.get('name', '').lower()
                values = desc.get('values', [])
                if values:
                    value = values[0].get('content', '')

                    if 'grader' in name or 'certification' in name:
                        result['grading_company'] = value
                    elif 'grade' in name:
                        result['grade'] = value
                    elif 'cert' in name or 'serial' in name:
                        result['cert_number'] = value

        # Fall back to title parsing
        if not result['grading_company']:
            grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC)\s+(\d+(?:\.\d+)?)\b'
            match = re.search(grading_pattern, title, re.IGNORECASE)

            if match:
                company = match.group(1)
                grade = match.group(2)

                company_map = {
                    'BGS': 'Beckett',
                    'BECKETT': 'Beckett'
                }
                result['grading_company'] = company_map.get(company.upper(), company)
                result['grade'] = grade

        # Try to extract cert number from title
        if not result['cert_number']:
            cert_pattern = r'#?\s*(\d{7,10})\b'  # 7-10 digit numbers are usually cert numbers
            cert_match = re.search(cert_pattern, title)
            if cert_match:
                result['cert_number'] = cert_match.group(1)

        return result

    def extract_category(self, title: str, category_path: str = None) -> Optional[str]:
        """Extract sport/category from title or category path."""
        if category_path:
            path_lower = category_path.lower()
            if 'basketball' in path_lower:
                return 'Basketball'
            elif 'football' in path_lower:
                return 'Football'
            elif 'baseball' in path_lower:
                return 'Baseball'
            elif 'hockey' in path_lower:
                return 'Hockey'
            elif 'soccer' in path_lower:
                return 'Soccer'
            elif 'pokemon' in path_lower:
                return 'Pokemon'
            elif 'magic' in path_lower or 'mtg' in path_lower:
                return 'Magic The Gathering'

        # Fall back to title analysis
        categories = {
            'Basketball': ['Basketball', 'NBA', 'Kobe', 'Jordan', 'LeBron'],
            'Football': ['Football', 'NFL', 'Brady', 'Mahomes'],
            'Baseball': ['Baseball', 'MLB', 'Ohtani', 'Trout'],
            'Hockey': ['Hockey', 'NHL', 'Gretzky'],
            'Soccer': ['Soccer', 'FIFA', 'Messi', 'Ronaldo'],
            'Pokemon': ['Pokemon', 'Pikachu', 'Charizard'],
            'Magic The Gathering': ['Magic', 'MTG'],
        }

        title_upper = title.upper()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.upper() in title_upper:
                    return category

        return None

    @retry_async(max_retries=3, delay=1.0)
    async def search_auctions(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        category_id: str = None,
        query: str = None,
        offset: int = 0,
        limit: int = 200
    ) -> dict:
        """Search for auction listings using eBay Browse API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        }

        params = {
            "limit": min(limit, 200),  # eBay max is 200
            "offset": offset,
            "filter": "buyingOptions:{AUCTION}",  # Auctions only
            "sort": "endingSoonest",  # Show auctions ending soon first
            "fieldgroups": "EXTENDED"  # Get additional fields
        }

        if category_id:
            params["category_ids"] = category_id

        if query:
            params["q"] = query
        else:
            # Default search for trading cards
            params["q"] = "trading cards"

        response = await client.get(
            self.browse_url,
            headers=headers,
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def normalize_item(self, ebay_item: dict) -> dict:
        """Convert eBay item to our standard format."""
        title = ebay_item.get('title', '')

        # Get image URL
        image_url = None
        if ebay_item.get('image'):
            image_url = ebay_item['image'].get('imageUrl')
        elif ebay_item.get('thumbnailImages'):
            image_url = ebay_item['thumbnailImages'][0].get('imageUrl')

        # Get current bid or price
        current_bid = None
        if ebay_item.get('currentBidPrice'):
            current_bid = float(ebay_item['currentBidPrice'].get('value', 0))
        elif ebay_item.get('price'):
            current_bid = float(ebay_item['price'].get('value', 0))

        # Get bid count
        bid_count = ebay_item.get('bidCount', 0)

        # Get end time
        end_time = None
        if ebay_item.get('itemEndDate'):
            try:
                end_time = datetime.fromisoformat(
                    ebay_item['itemEndDate'].replace('Z', '+00:00')
                )
            except:
                pass

        # Extract grading info
        condition_descriptors = ebay_item.get('conditionDescriptors', [])
        grading_info = self.extract_grading_info(title, condition_descriptors)

        # Get category
        category_path = None
        if ebay_item.get('categories'):
            category_path = ' > '.join([c.get('categoryName', '') for c in ebay_item['categories']])
        category = self.extract_category(title, category_path)

        # Detect sport from item content
        description = ebay_item.get('shortDescription', '')
        sport = detect_sport_from_item(title, description, category).value

        # Build item URL
        item_url = ebay_item.get('itemWebUrl') or ebay_item.get('itemHref')

        # Get item ID (strip the version suffix if present)
        item_id = ebay_item.get('itemId', '')
        external_id = item_id.split('|')[0] if '|' in item_id else item_id

        # Get seller info
        seller = ebay_item.get('seller', {})
        seller_name = seller.get('username', '')

        return {
            "external_id": external_id,
            "lot_number": None,  # eBay doesn't use lot numbers
            "cert_number": grading_info['cert_number'],
            "sub_category": category,
            "grading_company": grading_info['grading_company'],
            "grade": grading_info['grade'],
            "title": title[:500] if title else "",
            "description": description,
            "category": category,
            "sport": sport,
            "image_url": image_url,
            "current_bid": current_bid,
            "starting_bid": None,
            "bid_count": bid_count,
            "end_time": end_time,
            "status": "Live",
            "item_url": item_url,
            "raw_data": {
                "ebay": ebay_item,
                "seller": seller_name,
                "condition": ebay_item.get('condition'),
                "location": ebay_item.get('itemLocation', {}).get('country')
            }
        }

    async def scrape(self, db: AsyncSession, max_items: int = 5000) -> list:
        """Main scraping function - fetches auction listings from eBay."""
        print("🔍 Fetching auction items from eBay...")

        if not self.client_id or not self.client_secret:
            print("⚠️ eBay API credentials not configured!")
            print("   Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET environment variables")
            print("   Get credentials at: https://developer.ebay.com/")
            return []

        async with httpx.AsyncClient() as client:
            # Get access token
            print("📡 Step 1: Getting eBay access token...")
            try:
                access_token = await self.get_access_token(client)
            except Exception as e:
                print(f"❌ Failed to get access token: {e}")
                return []

            # Fetch items from each category
            print("📡 Step 2: Searching for auction listings...")

            all_items = []
            seen_ids = set()

            # Search queries for different card types
            search_queries = [
                "sports trading cards",
                "pokemon cards",
                "baseball cards PSA",
                "basketball cards BGS",
                "football cards graded",
            ]

            for query in search_queries:
                if len(all_items) >= max_items:
                    break

                print(f"\n   Searching: '{query}'...")
                offset = 0

                while len(all_items) < max_items:
                    try:
                        response = await self.search_auctions(
                            client,
                            access_token,
                            query=query,
                            offset=offset,
                            limit=200
                        )

                        items = response.get('itemSummaries', [])
                        total = response.get('total', 0)

                        if offset == 0:
                            print(f"   Found {total} auctions for '{query}'")

                        if not items:
                            break

                        # Deduplicate and add items
                        new_count = 0
                        for item in items:
                            item_id = item.get('itemId', '').split('|')[0]
                            if item_id and item_id not in seen_ids:
                                seen_ids.add(item_id)
                                all_items.append(item)
                                new_count += 1

                        print(f"   Offset {offset}: Got {len(items)}, {new_count} new (total: {len(all_items)})")

                        # Check if we've gotten all items
                        offset += len(items)
                        if offset >= total or len(items) < 200:
                            break

                        # Rate limiting
                        await asyncio.sleep(0.5)

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:
                            print("   ⚠️ Rate limited, waiting 30s...")
                            await asyncio.sleep(30)
                        else:
                            print(f"   ❌ Error: {e}")
                            break
                    except Exception as e:
                        print(f"   ❌ Error: {e}")
                        break

            items_to_process = all_items[:max_items]
            print(f"\n✅ Fetched {len(items_to_process)} unique auction items")

            # Normalize items
            print("\n📡 Step 3: Normalizing items...")
            normalized_items = []
            for item in items_to_process:
                try:
                    normalized = self.normalize_item(item)
                    normalized_items.append(normalized)
                except Exception as e:
                    print(f"   ⚠️ Error normalizing item: {e}")

            print(f"   ✅ Normalized {len(normalized_items)} items")

            # Create or update auction record
            print("\n📦 Creating/updating auction record...")
            auction_external_id = "ebay-auctions"

            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == "ebay",
                    Auction.external_id == auction_external_id
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                auction = Auction(
                    auction_house="ebay",
                    external_id=auction_external_id,
                    title="eBay Auctions",
                    status="active"
                )
                db.add(auction)
                await db.flush()

            print(f"✅ Auction ID: {auction.id}")

            # Save items to database
            print(f"\n💾 Saving {len(normalized_items)} items to database...")

            saved_count = 0
            for item_data in normalized_items:
                try:
                    result = await db.execute(
                        select(AuctionItem).where(
                            AuctionItem.auction_house == "ebay",
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
                            auction_house="ebay",
                            **item_data
                        )
                        db.add(item)

                    saved_count += 1
                except Exception as e:
                    print(f"   ⚠️ Error saving item {item_data.get('external_id')}: {e}")

            await db.commit()
            print(f"✅ Saved {saved_count} items to database")

            return normalized_items

    async def health_check(self) -> HealthCheckResult:
        """Check if eBay API is accessible."""
        if not self.client_id or not self.client_secret:
            return HealthCheckResult(
                healthy=False,
                message="eBay API credentials not configured",
                details={"error": "Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET"}
            )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                access_token = await self.get_access_token(client)

                # Try a simple search
                response = await self.search_auctions(
                    client,
                    access_token,
                    query="trading cards",
                    limit=1
                )

                total = response.get('total', 0)
                mode = "Sandbox" if self.sandbox else "Production"
                return HealthCheckResult(
                    healthy=True,
                    message=f"eBay Browse API is accessible ({mode})",
                    details={"total_auctions": total, "mode": mode}
                )

        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"eBay API error: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper."""
    await init_db()

    scraper = EbayScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")

        graded_items = [item for item in items if item.get('grading_company')]
        print(f"   Items with grading data: {len(graded_items)}")


if __name__ == "__main__":
    asyncio.run(main())
