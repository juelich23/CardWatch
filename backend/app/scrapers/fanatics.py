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
from sqlalchemy import select, update
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

        # Note: The API key has embedded marketplace filters, so we only add status filter
        # The embedded filters already include: marketplace:WEEKLY OR marketplace:PREMIER OR marketplace:FIXED
        base_filter = 'status:"Live"'
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
                        "currentBid",
                        "startingBid",
                        "status",
                        "images",
                        "lotNumber",
                        "bidCount",
                        "auctionEndDatetime",
                        "auctionName",
                        "gradingService",
                        "grade",
                        "serial",
                        "category",
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

    @staticmethod
    def _format_grade(grade) -> Optional[str]:
        """Algolia returns grade as a number (10, 9.5) or None -> store as a clean string."""
        if grade is None or grade == "":
            return None
        try:
            f = float(grade)
            return str(int(f)) if f.is_integer() else str(f)
        except (TypeError, ValueError):
            return str(grade)

    def normalize_item(self, algolia_item: dict, details: Optional[dict] = None) -> dict:
        """Convert a Fanatics Algolia hit to our standard format.

        All required fields are present in the Algolia search response, so a
        per-item GraphQL `details` fetch is no longer needed. `details` is kept
        as an optional argument for backward compatibility and, when supplied,
        its richer fields take precedence.
        """
        title = algolia_item.get('title', '') or ''
        subtitle = algolia_item.get('subtitle', '')

        # Grading: prefer Algolia's structured fields, fall back to parsing the title.
        company_map = {'BGS': 'Beckett', 'BECKETT': 'Beckett'}
        grading_company = algolia_item.get('gradingService')
        if grading_company:
            grading_company = company_map.get(grading_company.upper(), grading_company)
        grade = self._format_grade(algolia_item.get('grade'))
        cert_number = algolia_item.get('serial')

        if not grading_company or not grade:
            parsed = self.extract_grading_info(title, None)
            grading_company = grading_company or parsed['grading_company']
            grade = grade or parsed['grade']

        # Pricing. currentPrice is the effective price (= current bid, or starting
        # bid when there are no bids yet). currentBid is 0 until the first bid.
        current_price = algolia_item.get('currentPrice')
        if current_price is None:
            current_price = algolia_item.get('currentBid') or 0
        starting_price = algolia_item.get('startingBid')

        # End time: Algolia gives a unix timestamp (UTC).
        end_time = None
        ts = algolia_item.get('auctionEndDatetime')
        if ts:
            try:
                end_time = datetime.utcfromtimestamp(int(ts))
            except (TypeError, ValueError, OSError):
                pass
        # Detail fetch (if ever provided) carries an explicit ISO end time.
        if details and details.get('auction') and details['auction'].get('endsAt'):
            try:
                end_time = datetime.fromisoformat(details['auction']['endsAt'].replace('Z', '+00:00'))
            except ValueError:
                pass

        # Image URL: primary.large, falling back to secondary.large.
        image_url = None
        images = algolia_item.get('images') or {}
        if isinstance(images, dict):
            for group in ('primary', 'secondary'):
                g = images.get(group)
                if isinstance(g, dict) and g.get('large'):
                    image_url = g['large']
                    break

        # Build item URL. The UUID-only URL redirects to the slugged canonical URL.
        listing_uuid = algolia_item['listingUuid']
        marketplace = (algolia_item.get('marketplace') or 'WEEKLY').lower()
        item_url = f"{self.base_url}/{marketplace}/{listing_uuid}" if listing_uuid else None

        # Category: Algolia provides a clean sport/category; fall back to title parsing.
        category = algolia_item.get('category') or self.extract_category(title + ' ' + (subtitle or ''))
        sport = detect_sport_from_item(title, subtitle, category).value

        return {
            "external_id": listing_uuid,
            "lot_number": algolia_item.get('lotNumber'),
            "cert_number": cert_number,
            "sub_category": category,
            "grading_company": grading_company,
            "grade": grade,
            "title": title[:500],
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
            "raw_data": {"algolia": algolia_item},
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

    # Attributes pulled from Algolia - everything normalize_item needs, so no
    # per-item GraphQL detail fetch is required.
    BROWSE_ATTRIBUTES = [
        "listingUuid", "marketplace", "marketplaceSource", "title", "subtitle",
        "currentPrice", "currentBid", "startingBid", "status", "images",
        "lotNumber", "bidCount", "auctionEndDatetime", "auctionName",
        "gradingService", "grade", "serial", "category",
    ]

    async def browse_all_hits(self, client: httpx.AsyncClient, api_key: str, max_items: int) -> list:
        """Fetch ALL live hits using Algolia's cursor-based browse endpoint.

        Standard search pagination is capped (`paginationLimitedTo`, ~3000 hits)
        regardless of the true match count, so it cannot retrieve the full
        ~155k live weekly auction catalog. The browse endpoint walks the entire
        result set via an opaque cursor with no such cap.
        """
        import json as _json
        import urllib.parse

        browse_url = (
            f"https://{self.algolia_app_id.lower()}-dsn.algolia.net"
            f"/1/indexes/prod_item_state_v1/browse"
        )
        params = {
            "x-algolia-api-key": api_key,
            "x-algolia-application-id": self.algolia_app_id,
        }
        # filters + attributes only need to be sent on the first request; the
        # cursor carries the query context on subsequent requests.
        # Restrict to auction marketplaces (WEEKLY/PREMIER). The browse endpoint
        # does NOT honor the embedded marketplace filter on the search key, so
        # without this it also returns the ~160k FIXED-price (buy-it-now) listings
        # which are not auctions and have no end time.
        initial_query = urllib.parse.urlencode({
            "filters": 'status:"Live" AND (marketplace:WEEKLY OR marketplace:PREMIER)',
            "hitsPerPage": 1000,
            "attributesToRetrieve": _json.dumps(self.BROWSE_ATTRIBUTES),
        })

        all_hits = []
        seen_uuids = set()
        cursor = None
        page = 0

        while len(all_hits) < max_items:
            body = {"cursor": cursor} if cursor else {"params": initial_query}

            data = None
            for attempt in range(3):
                try:
                    response = await client.post(browse_url, params=params, json=body, timeout=60.0)
                    response.raise_for_status()
                    data = response.json()
                    break
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    if attempt == 2:
                        raise
                    print(f"   ⚠️ Browse request failed: {e}. Retrying...")
                    await asyncio.sleep(1.0 * (attempt + 1))

            hits = data.get("hits", [])
            for hit in hits:
                uuid = hit.get("listingUuid")
                if uuid and uuid not in seen_uuids:
                    seen_uuids.add(uuid)
                    all_hits.append(hit)

            page += 1
            print(f"   Browse page {page}: +{len(hits)} hits (unique total: {len(all_hits)})")

            cursor = data.get("cursor")
            if not cursor or not hits:
                break

        return all_hits[:max_items]

    async def scrape(self, db: AsyncSession, max_items: int = 200000) -> list:
        """Main scraping function - fetches ALL items (cards, memorabilia, autographs, etc.)"""
        print("🔍 Fetching items from Fanatics Collect...")

        async with httpx.AsyncClient() as client:
            # Step 0: Fetch fresh API key
            print("📡 Step 0: Fetching fresh Algolia API key...")
            api_key = await self.fetch_search_key(client)

            # Step 1: Fetch ALL live items via the cursor-based browse endpoint.
            # Standard search pagination caps out at ~3000 hits regardless of the
            # true match count, so it cannot retrieve the full ~155k live catalog.
            print("📡 Step 1: Browsing ALL live items from Algolia...")
            hits = await self.browse_all_hits(client, api_key, max_items)
            print(f"✅ Fetched {len(hits)} unique items")

            # Step 2: Normalize directly from the Algolia hits.
            # Every field we need (end time, bids, grading, cert#, images) is in the
            # search response, so no per-item GraphQL detail fetch is required. This
            # is what makes a full pull of all live weekly auctions feasible.
            print("\n📡 Step 2: Normalizing items from Algolia data...")
            normalized_items = [self.normalize_item(item) for item in hits]
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

            # Record the scrape-start timestamp BEFORE any upsert. Every item we
            # touch (insert or update) will have updated_at >= this value, so any
            # still-"Live" Fanatics row left with an older updated_at after the
            # commit is no longer in the live catalog and should be marked Ended.
            scrape_start = datetime.utcnow()

            # Dedupe scraped items by external_id (browse already dedupes, but be
            # safe so the existence dict and the IN() queries stay consistent).
            items_by_id: Dict[str, dict] = {}
            for item_data in normalized_items:
                items_by_id[item_data["external_id"]] = item_data
            unique_items = list(items_by_id.values())
            scraped_external_ids = list(items_by_id.keys())

            # --- Batch the existence check (kill the N+1 SELECT-per-item) ---
            # Fetch all existing Fanatics rows for the scraped ids in chunked
            # IN() queries, building a {external_id: AuctionItem} dict in one pass
            # instead of one round-trip per item.
            existing_items: Dict[str, AuctionItem] = {}
            SELECT_CHUNK = 1000
            for chunk_start in range(0, len(scraped_external_ids), SELECT_CHUNK):
                id_chunk = scraped_external_ids[chunk_start:chunk_start + SELECT_CHUNK]
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == "fanatics",
                        AuctionItem.external_id.in_(id_chunk)
                    )
                )
                for row in result.scalars().all():
                    existing_items[row.external_id] = row

            print(f"   ... {len(unique_items)} items ({len(existing_items)} existing, "
                  f"{len(unique_items) - len(existing_items)} new)")

            # --- Upsert in chunks, committing periodically ---
            new_count = 0
            update_count = 0
            COMMIT_CHUNK = 1000
            for batch_start in range(0, len(unique_items), COMMIT_CHUNK):
                batch = unique_items[batch_start:batch_start + COMMIT_CHUNK]

                for item_data in batch:
                    existing_item = existing_items.get(item_data["external_id"])

                    if existing_item:
                        # Update existing item (same fields as before)
                        for key, value in item_data.items():
                            if key not in ['external_id', 'auction_house']:
                                setattr(existing_item, key, value)
                        # Explicitly bump updated_at so it's guaranteed >= scrape_start
                        existing_item.updated_at = datetime.utcnow()
                        update_count += 1
                    else:
                        # Create new item. updated_at uses the model default
                        # (datetime.utcnow), so new rows are also >= scrape_start.
                        item = AuctionItem(
                            auction_id=auction.id,
                            auction_house="fanatics",
                            **item_data
                        )
                        db.add(item)
                        new_count += 1

                await db.commit()

            print(f"✅ Saved {len(unique_items)} items "
                  f"({new_count} new, {update_count} updated)")

            # --- Mark stale rows ended ---
            # Fanatics' browse returns the COMPLETE set of live weekly/premier
            # auctions, so any existing Fanatics row that is still "Live" but was
            # NOT touched this run (updated_at < scrape_start, or NULL) is no longer
            # live. This updated_at-cutoff approach avoids a 40k-element NOT IN()
            # clause and is safe because every scraped item above had its
            # updated_at set to >= scrape_start (inserts via the model default,
            # updates explicitly).
            stale_result = await db.execute(
                update(AuctionItem)
                .where(
                    AuctionItem.auction_house == "fanatics",
                    AuctionItem.status != "Ended",
                    (AuctionItem.updated_at < scrape_start) | (AuctionItem.updated_at.is_(None)),
                )
                .values(status="Ended", updated_at=datetime.utcnow())
            )
            await db.commit()
            print(f"🏁 Marked {stale_result.rowcount} stale Fanatics items as Ended")

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
