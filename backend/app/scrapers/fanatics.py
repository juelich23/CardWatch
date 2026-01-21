#!/usr/bin/env python3
"""
Fanatics Collect Scraper
Fetches auction items from Fanatics Collect using their Algolia search and GraphQL APIs
"""

import asyncio
import httpx
import re
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult, retry_async
from app.utils.sport_detection import detect_sport_from_item


class FanaticsScraper:
    def __init__(self):
        self.algolia_app_id = "3XT9C4X62I"  # Static app ID
        self.algolia_api_key = None  # Fetched dynamically
        self.algolia_url = f"https://{self.algolia_app_id.lower()}-dsn.algolia.net/1/indexes/*/queries"
        self.graphql_url = "https://app.fanaticscollect.com/graphql"
        self.base_url = "https://www.fanaticscollect.com"

    async def fetch_search_key(self, client: httpx.AsyncClient) -> str:
        """Fetch a fresh Algolia search key from the GraphQL API."""
        headers = {
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': 'https://www.fanaticscollect.com',
            'referer': 'https://www.fanaticscollect.com/',
            'x-platform': 'WEB',
            'x-platform-app': 'collect',
        }

        payload = {
            "operationName": "webSearchKeyQuery",
            "query": "query webSearchKeyQuery { collectSearchKey }"
        }

        response = await client.post(
            f"{self.graphql_url}?webSearchKeyQuery",
            headers=headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()

        key = data.get('data', {}).get('collectSearchKey')
        if not key:
            raise ValueError("No search key returned from GraphQL API")

        print(f"   Fetched fresh Algolia search key (expires based on validUntil)")
        return key

    def extract_grading_info(self, title: str, grading_url: Optional[str]) -> dict:
        """Extract grading company, grade, and cert number from title and URL"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        # Extract grading company and grade from title
        # Examples: "PSA 10", "BGS 9.5", "SGC 9"
        grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC)\s+(\d+(?:\.\d+)?)\b'
        match = re.search(grading_pattern, title, re.IGNORECASE)

        if match:
            company = match.group(1)
            grade = match.group(2)

            # Normalize grading company names
            company_map = {
                'BGS': 'Beckett',
                'BECKETT': 'Beckett'
            }
            result['grading_company'] = company_map.get(company.upper(), company)
            result['grade'] = grade

        # Extract cert number from grading service URL
        if grading_url:
            # PSA: https://www.psacard.com/cert/25569000/psa
            psa_match = re.search(r'psacard\.com/cert/(\d+)', grading_url)
            if psa_match:
                result['cert_number'] = psa_match.group(1)
                if not result['grading_company']:
                    result['grading_company'] = 'PSA'

            # Beckett: https://www.beckett.com/grading/card-lookup?cert=XXXXXX
            beckett_match = re.search(r'beckett\.com/.*cert[=/](\d+)', grading_url)
            if beckett_match:
                result['cert_number'] = beckett_match.group(1)
                if not result['grading_company']:
                    result['grading_company'] = 'Beckett'

        return result

    def extract_category(self, title: str) -> Optional[str]:
        """Extract sport/category from title"""
        categories = {
            'Basketball': ['Basketball', 'NBA', 'Kobe', 'Jordan', 'LeBron'],
            'Football': ['Football', 'NFL'],
            'Baseball': ['Baseball', 'MLB'],
            'Hockey': ['Hockey', 'NHL'],
            'Soccer': ['Soccer', 'Football Card', 'MLS'],
            'Pokemon': ['Pokemon', 'Pikachu'],
            'Magic The Gathering': ['Magic', 'MTG'],
            'Yu-Gi-Oh': ['Yu-Gi-Oh', 'YuGiOh']
        }

        title_upper = title.upper()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.upper() in title_upper:
                    return category

        return None

    @retry_async(max_retries=3, delay=1.0)
    async def fetch_algolia_items(self, client: httpx.AsyncClient, api_key: str, page: int = 0, hits_per_page: int = 1000, extra_filter: str = None) -> dict:
        """Fetch items from Algolia search API"""
        params = {
            "x-algolia-agent": "Algolia for JavaScript (5.13.0); Search (5.13.0); Browser",
            "x-algolia-api-key": api_key,
            "x-algolia-application-id": self.algolia_app_id
        }

        # Build filter string - fetch both WEEKLY and PREMIER marketplaces
        base_filter = '(marketplace:"WEEKLY" OR marketplace:"PREMIER") AND (status:"Live")'
        if extra_filter:
            filters = f'{base_filter} AND {extra_filter}'
        else:
            filters = base_filter

        payload = {
            "requests": [
                {
                    "indexName": "prod_item_state_v1",
                    "query": "",
                    "type": "default",
                    "page": page,
                    "hitsPerPage": hits_per_page,
                    "facets": ["*"],
                    "clickAnalytics": True,
                    "attributesToRetrieve": [
                        "listingUuid",
                        "marketplace",
                        "marketplaceSource",
                        "title",
                        "subtitle",
                        "currentPrice",
                        "status",
                        "images.primary",
                        "lotNumber",
                        "bidCount"
                    ],
                    "attributesToHighlight": [],
                    "filters": filters,
                    "numericFilters": []
                }
            ]
        }

        response = await client.post(self.algolia_url, params=params, json=payload, timeout=30.0)
        response.raise_for_status()
        return response.json()

    @retry_async(max_retries=2, delay=0.5)
    async def fetch_item_details(self, client: httpx.AsyncClient, listing_uuid: str, marketplace: str = "WEEKLY") -> Optional[dict]:
        """Fetch detailed item information from GraphQL API"""
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://www.fanaticscollect.com',
            'referer': 'https://www.fanaticscollect.com/',
            'x-platform': 'WEB',
            'x-platform-app': 'collect',
        }

        # Use the correct marketplace type for the GraphQL query
        listing_type = marketplace.upper() if marketplace else "WEEKLY"

        payload = {
            "operationName": "webWeeklyListingQuery",
            "variables": {
                "id": listing_uuid,
                "type": listing_type
            },
            "query": """query webWeeklyListingQuery($id: UUID!, $type: CollectListingType!) {
  collectListing(id: $id, type: $type) {
    id
    title
    currentBid {
      amountInCents
      currency
    }
    auction {
      name
      shortName
      endsAt
    }
    startingPrice {
      amountInCents
      currency
    }
    lotString
    imageSets {
      large
      medium
      small
      thumbnail
    }
    slug
    subtitle
    description
    status
    bidCount
    vaultItem {
      gradingServiceUrl
    }
  }
}"""
        }

        try:
            response = await client.post(f"{self.graphql_url}?webWeeklyListingQuery", headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and 'collectListing' in data['data']:
                return data['data']['collectListing']
            return None
        except Exception as e:
            print(f"   ⚠️ Error fetching details for {listing_uuid}: {e}")
            return None

    def normalize_item(self, algolia_item: dict, details: Optional[dict]) -> dict:
        """Convert Fanatics item to our standard format"""
        title = algolia_item.get('title', '')
        subtitle = algolia_item.get('subtitle', '')

        # Extract grading information
        grading_url = None
        if details and details.get('vaultItem'):
            grading_url = details['vaultItem'].get('gradingServiceUrl')

        grading_info = self.extract_grading_info(title, grading_url)

        # Get price in dollars
        current_price = algolia_item.get('currentPrice', 0)
        if details and details.get('currentBid'):
            current_price = details['currentBid'].get('amountInCents', 0) / 100

        starting_price = None
        if details and details.get('startingPrice'):
            starting_price = details['startingPrice'].get('amountInCents', 0) / 100

        # Get end time
        end_time = None
        if details and details.get('auction') and details['auction'].get('endsAt'):
            end_time_str = details['auction']['endsAt']
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except:
                pass

        # Get image URL
        image_url = None
        if algolia_item.get('images') and algolia_item['images'].get('primary'):
            image_url = algolia_item['images']['primary'].get('large')
        elif details and details.get('imageSets') and len(details['imageSets']) > 0:
            image_url = details['imageSets'][0].get('large')

        # Build item URL
        # URL format: https://www.fanaticscollect.com/{type}/{listingUuid}/{slug}
        # Type is "weekly" or "premier" depending on marketplace
        listing_uuid = algolia_item['listingUuid']
        marketplace = algolia_item.get('marketplace', 'WEEKLY').lower()
        slug = details.get('slug') if details else None
        item_url = None
        if listing_uuid:
            if slug:
                item_url = f"{self.base_url}/{marketplace}/{listing_uuid}/{slug}"
            else:
                # Fallback: use just the UUID (will redirect to proper URL)
                item_url = f"{self.base_url}/{marketplace}/{listing_uuid}"

        # Extract category
        category = self.extract_category(title + ' ' + (subtitle or ''))

        # Detect sport from item content
        sport = detect_sport_from_item(title, subtitle, category).value

        return {
            "external_id": algolia_item['listingUuid'],
            "lot_number": algolia_item.get('lotNumber'),
            "cert_number": grading_info['cert_number'],
            "sub_category": category,
            "grading_company": grading_info['grading_company'],
            "grade": grading_info['grade'],
            "title": title[:500] if title else "",
            "description": subtitle,
            "category": category,
            "sport": sport,
            "image_url": image_url,
            "current_bid": current_price,
            "starting_bid": starting_price,
            "bid_count": algolia_item.get('bidCount', 0),
            "end_time": end_time,
            "status": "Live",
            "item_url": item_url,
            "raw_data": {
                "algolia": algolia_item,
                "details": details
            }
        }

    async def _fetch_category_items(self, client: httpx.AsyncClient, api_key: str, category_filter: str, category_name: str, max_per_category: int = 10000) -> list:
        """Fetch all items for a specific category with pagination"""
        all_hits = []
        page = 0
        page_size = 1000

        while len(all_hits) < max_per_category:
            algolia_response = await self.fetch_algolia_items(
                client, api_key, page=page, hits_per_page=page_size, extra_filter=category_filter
            )

            result = algolia_response['results'][0]
            page_hits = result['hits']
            total_in_category = result['nbHits']

            if page == 0:
                print(f"   {category_name}: {total_in_category} items available")

            if not page_hits:
                break

            all_hits.extend(page_hits)

            if len(all_hits) >= total_in_category or len(page_hits) < page_size:
                break

            page += 1

        return all_hits

    async def scrape(self, db: AsyncSession, max_items: int = 50000) -> list:
        """Main scraping function - fetches ALL items (cards, memorabilia, autographs, etc.)"""
        print("🔍 Fetching items from Fanatics Collect...")

        async with httpx.AsyncClient() as client:
            # Step 0: Fetch fresh API key
            print("📡 Step 0: Fetching fresh Algolia API key...")
            api_key = await self.fetch_search_key(client)

            # Step 1: Fetch ALL items - no category filtering
            # We use pagination to get all items rather than filtering by subcategory
            print("📡 Step 1: Getting ALL items from Algolia (no category filter)...")

            all_hits = []
            seen_uuids = set()
            page = 0
            page_size = 1000

            while len(all_hits) < max_items:
                algolia_response = await self.fetch_algolia_items(
                    client, api_key, page=page, hits_per_page=page_size, extra_filter=None
                )

                result = algolia_response['results'][0]
                page_hits = result['hits']
                total_available = result['nbHits']

                if page == 0:
                    print(f"   Total available: {total_available} items")

                if not page_hits:
                    break

                # Deduplicate
                new_hits = 0
                for hit in page_hits:
                    uuid = hit.get('listingUuid')
                    if uuid and uuid not in seen_uuids:
                        seen_uuids.add(uuid)
                        all_hits.append(hit)
                        new_hits += 1

                print(f"   Page {page + 1}: Got {len(page_hits)} items, {new_hits} new (total: {len(all_hits)})")

                if len(all_hits) >= total_available or len(page_hits) < page_size:
                    break

                page += 1

            hits = all_hits[:max_items]
            print(f"✅ Fetched {len(hits)} unique items")

            # Fetch details for each item
            print("\n📡 Step 2: Fetching detailed item information...")
            print(f"🚀 Fetching details for {len(hits)} items concurrently...")

            # Create tasks for concurrent fetching
            semaphore = asyncio.Semaphore(50)  # Limit concurrent requests

            async def fetch_with_details(algolia_item):
                async with semaphore:
                    marketplace = algolia_item.get('marketplace', 'WEEKLY')
                    details = await self.fetch_item_details(client, algolia_item['listingUuid'], marketplace)
                    return (algolia_item, details)

            tasks = [fetch_with_details(item) for item in hits]

            normalized_items = []
            completed = 0

            for coro in asyncio.as_completed(tasks):
                algolia_item, details = await coro
                normalized_item = self.normalize_item(algolia_item, details)
                normalized_items.append(normalized_item)

                completed += 1
                if completed % 100 == 0:
                    print(f"   Progress: {completed}/{len(hits)}")

            print(f"   ✅ Completed: {len(normalized_items)} items normalized")

            # Create or update auction
            print("\n📦 Creating/updating auction record...")
            auction_external_id = "fanatics-collect"

            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == "fanatics",
                    Auction.external_id == auction_external_id
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                auction = Auction(
                    auction_house="fanatics",
                    external_id=auction_external_id,
                    title="Fanatics Collect Auctions",
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
                        AuctionItem.auction_house == "fanatics",
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
                        auction_house="fanatics",
                        **item_data
                    )
                    db.add(item)

            await db.commit()
            print(f"✅ Saved {len(normalized_items)} items to database")

            return normalized_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Fanatics APIs are reachable"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # First, try to get a fresh API key
                try:
                    api_key = await self.fetch_search_key(client)
                except Exception as e:
                    return HealthCheckResult(
                        healthy=False,
                        message=f"Failed to fetch Algolia search key: {str(e)}",
                        details={"error": str(e)}
                    )

                # Now test the Algolia API with the fresh key
                params = {
                    "x-algolia-api-key": api_key,
                    "x-algolia-application-id": self.algolia_app_id
                }
                payload = {
                    "requests": [{
                        "indexName": "prod_item_state_v1",
                        "query": "",
                        "hitsPerPage": 1
                    }]
                }
                response = await client.post(
                    self.algolia_url,
                    params=params,
                    json=payload,
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if 'results' in data and len(data['results']) > 0:
                        return HealthCheckResult(
                            healthy=True,
                            message="Fanatics Algolia API is reachable",
                            details={"total_hits": data['results'][0].get('nbHits', 0)}
                        )
                return HealthCheckResult(
                    healthy=False,
                    message=f"Fanatics API returned unexpected response",
                    details={"status_code": response.status_code}
                )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Fanatics API unreachable: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper"""
    # Initialize database
    await init_db()

    scraper = FanaticsScraper()

    # Get database session
    async for db in get_db():
        items = await scraper.scrape(db, max_items=1000)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")

        # Count items with grading data
        graded_items = [item for item in items if item.get('grading_company')]
        print(f"   Items with grading data: {len(graded_items)}")


if __name__ == "__main__":
    asyncio.run(main())
