import asyncio
import httpx
import re
from typing import List, Dict, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.scrapers.base import BaseScraper, retry_async, HealthCheckResult
from app.models import Auction, AuctionItem
from app.utils.sport_detection import detect_sport_from_item


class GoldinHTTPScraper(BaseScraper):
    """
    HTTP-based scraper for Goldin (no browser needed!)
    Extracts data from embedded Redux state in the HTML
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        super().__init__(db)
        self.auction_house_name = "goldin"
        self.base_url = "https://goldin.co"
        self.client = None

    async def __aenter__(self):
        """Create HTTP client"""
        self.client = httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            },
            follow_redirects=True,
            timeout=30.0
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()

    async def scrape_active_auctions(self) -> List[Dict]:
        """Get active auctions"""
        return [{
            "auction_house": "goldin",
            "external_id": "current",
            "title": "Goldin Current Auctions",
            "status": "active",
        }]

    async def scrape_auction_items(self, auction_id: str = None, max_items: int = 5000) -> List[Dict]:
        """
        Scrape auction items using Goldin's lots_v2 API with pagination
        """
        print(f"\n🔍 Fetching lots from Goldin API...")

        try:
            # First, get all auction IDs
            print("📡 Step 1: Getting auction IDs...")
            auctions_url = "https://d2l9s2774i83t9.cloudfront.net/api/auctions"

            auctions_response = await self.client.post(
                auctions_url,
                json={"status": "All", "order": "asc"},
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': 'https://goldin.co',
                    'Referer': 'https://goldin.co/',
                },
                timeout=30.0
            )

            auctions_data = auctions_response.json()
            auction_ids = [a['auction_id'] for a in auctions_data.get('auctions', [])]
            print(f"✅ Got {len(auction_ids)} auction IDs")

            # Now get the actual lots with pagination
            print("\n📡 Step 2: Getting lots from all auctions (with pagination)...")
            lots_url = "https://d1wu47wucybvr3.cloudfront.net/api/lots_v2"

            all_items = []
            page_size = 1000
            offset = 0
            total_available = None

            while len(all_items) < max_items:
                # Build payload - get ALL item types (cards, memorabilia, autographs, etc.)
                payload = {
                    "search": {
                        "queryType": "Featured",
                        "size": page_size,
                        "from": offset,
                        "auction_id": auction_ids
                    }
                }

                print(f"📦 Fetching items {offset + 1} to {offset + page_size}...")

                # Make the API call
                response = await self.client.post(
                    lots_url,
                    json=payload,
                    headers={
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json',
                        'Origin': 'https://goldin.co',
                        'Referer': 'https://goldin.co/',
                    },
                    timeout=60.0
                )

                if response.status_code != 200:
                    print(f"❌ Bad status code: {response.status_code}")
                    break

                data = response.json()

                # Check for total count on first request
                if total_available is None and 'searchalgolia' in data:
                    sa = data['searchalgolia']
                    total_available = sa.get('nbHits') or sa.get('total') or sa.get('totalHits')
                    if total_available:
                        print(f"📊 Total available: {total_available} items")

                # Extract items from this page
                page_items = self._extract_lots_from_response(data)

                if not page_items:
                    print(f"   No more items found")
                    break

                all_items.extend(page_items)
                print(f"   Got {len(page_items)} items (total: {len(all_items)})")

                # Check if we've gotten all available items
                if total_available and len(all_items) >= total_available:
                    break

                # Check if this page had fewer items than requested (last page)
                if len(page_items) < page_size:
                    break

                offset += page_size

            print(f"✅ Extracted {len(all_items)} total lots from API")

            # Fetch cert numbers from /api/lots endpoint
            await self._fetch_cert_numbers(all_items, data)

            return all_items[:max_items]

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_lots_from_response(self, data: Dict) -> List[Dict]:
        """Extract lots from the lots_v2 API response"""
        items = []

        print("\n🔍 Analyzing lots response structure...")

        if isinstance(data, dict):
            print(f"Top-level keys: {list(data.keys())[:20]}")

            # Check for Goldin's searchalgolia structure first
            if 'searchalgolia' in data:
                print("✅ Found 'searchalgolia' in response")
                searchalgolia = data['searchalgolia']

                if isinstance(searchalgolia, dict) and 'lots' in searchalgolia:
                    lots = searchalgolia['lots']
                    if isinstance(lots, list):
                        print(f"   Found {len(lots)} lots in searchalgolia.lots array")
                        for lot in lots:
                            normalized = self._normalize_lot(lot)
                            if normalized.get('title'):
                                items.append(normalized)
                        return items

            # Fallback to common places to find lots
            for key in ['hits', 'results', 'lots', 'items', 'data']:
                if key in data:
                    lot_data = data[key]
                    print(f"✅ Found '{key}' in response")

                    if isinstance(lot_data, dict) and 'hits' in lot_data:
                        # Elasticsearch-style response
                        hits = lot_data['hits']
                        if isinstance(hits, list):
                            print(f"   Found {len(hits)} lots in hits array")
                            for hit in hits:
                                source = hit.get('_source', hit)
                                normalized = self._normalize_lot(source)
                                if normalized.get('title'):
                                    items.append(normalized)
                        elif isinstance(hits, dict) and 'hits' in hits:
                            # Nested hits
                            nested_hits = hits['hits']
                            print(f"   Found {len(nested_hits)} lots in nested hits")
                            for hit in nested_hits:
                                source = hit.get('_source', hit)
                                normalized = self._normalize_lot(source)
                                if normalized.get('title'):
                                    items.append(normalized)
                    elif isinstance(lot_data, list):
                        print(f"   Array with {len(lot_data)} items")
                        for lot in lot_data:
                            normalized = self._normalize_lot(lot)
                            if normalized.get('title'):
                                items.append(normalized)
                    break

        return items

    async def _fetch_cert_numbers(self, items: List[Dict], lots_data: Dict):
        """
        Fetch cert_numbers from /api/lots endpoint using meta_slugs.
        Updates items in-place with cert_number field.
        """
        print("\n📡 Step 3: Fetching cert numbers from /api/lots...")

        # Extract lots from response
        lots = []
        if isinstance(lots_data, dict) and 'searchalgolia' in lots_data:
            searchalgolia = lots_data['searchalgolia']
            if isinstance(searchalgolia, dict) and 'lots' in searchalgolia:
                lots = searchalgolia['lots']

        # Build mapping from slug to cert_number
        slug_to_cert = {}

        # Collect all meta_slugs
        slugs = [lot.get('meta_slug') for lot in lots if lot.get('meta_slug')]

        if not slugs:
            print("⚠️ No meta_slugs found to fetch cert numbers")
            return

        print(f"📦 Found {len(slugs)} slugs to fetch")
        print(f"🚀 Fetching cert_numbers concurrently (this will be fast)...")

        lots_url = "https://d1wu47wucybvr3.cloudfront.net/api/lots"

        async def fetch_cert_for_slug(slug: str) -> tuple[str, dict]:
            """Fetch grading data for a single slug"""
            try:
                response = await self.client.post(
                    lots_url,
                    json={"queryType": "Search", "slug": [slug]},
                    headers={
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json',
                        'Origin': 'https://goldin.co',
                        'Referer': 'https://goldin.co/',
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # Extract lots from response
                    response_lots = []
                    if isinstance(data, dict) and 'body' in data and isinstance(data['body'], dict):
                        response_lots = data['body'].get('lots', [])

                    # Get grading data and image from first lot
                    if response_lots and len(response_lots) > 0:
                        lot = response_lots[0]

                        # Try to extract image URL from detailed response
                        detail_image_url = None
                        primary_image_name = lot.get('primary_image_name')
                        detail_lot_id = lot.get('lot_id') or lot.get('id')
                        if primary_image_name and detail_lot_id:
                            detail_image_url = f"https://d2tt46f3mh26nl.cloudfront.net/public/Lots/{detail_lot_id}/{primary_image_name}@3x"

                        # Check images array
                        if not detail_image_url:
                            images = lot.get('images') or lot.get('lot_images') or []
                            if images and isinstance(images, list) and len(images) > 0:
                                first_image = images[0]
                                if isinstance(first_image, str):
                                    detail_image_url = first_image
                                elif isinstance(first_image, dict):
                                    detail_image_url = first_image.get('url') or first_image.get('image_url')

                        grading_data = {
                            'cert_number': lot.get('cert_number'),
                            'sub_category': lot.get('sub_category'),
                            'grading_company': lot.get('grading_company'),
                            'grade': str(lot.get('grade')) if lot.get('grade') is not None else None,
                            'image_url': detail_image_url,  # Include image from detailed response
                        }
                        return (slug, grading_data)

                return (slug, {})

            except Exception as e:
                print(f"   ⚠️ Error fetching {slug}: {e}")
                return (slug, {})

        # Fetch all cert_numbers concurrently with a semaphore to limit concurrent requests
        # Keep low to avoid exhausting Supabase connection pool
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        async def fetch_with_semaphore(slug: str):
            async with semaphore:
                return await fetch_cert_for_slug(slug)

        # Create tasks for all slugs
        tasks = [fetch_with_semaphore(slug) for slug in slugs]

        # Run all tasks concurrently and show progress
        completed = 0
        for coro in asyncio.as_completed(tasks):
            slug, grading_data = await coro
            if grading_data and grading_data.get('cert_number'):
                slug_to_cert[slug] = grading_data
            completed += 1
            if completed % 100 == 0:
                print(f"   Progress: {completed}/{len(slugs)} ({len(slug_to_cert)} with grading data)")

        print(f"   ✅ Completed: {completed}/{len(slugs)} fetched, {len(slug_to_cert)} have grading data")

        # Update items with grading data using the slug mapping
        grading_count = 0
        image_fixes = 0
        for item in items:
            raw_data = item.get('raw_data', {})
            meta_slug = raw_data.get('meta_slug')

            if meta_slug and meta_slug in slug_to_cert:
                grading_data = slug_to_cert[meta_slug]

                # Update item with all grading fields
                item['cert_number'] = grading_data.get('cert_number')
                item['sub_category'] = grading_data.get('sub_category')
                item['grading_company'] = grading_data.get('grading_company')
                item['grade'] = grading_data.get('grade')

                # If item is missing image_url, use the one from detailed response
                if not item.get('image_url') and grading_data.get('image_url'):
                    item['image_url'] = grading_data.get('image_url')
                    image_fixes += 1

                # Also update raw_data so it's stored in database
                raw_data.update(grading_data)
                grading_count += 1

        print(f"✅ Added grading data to {grading_count}/{len(items)} items")
        if image_fixes > 0:
            print(f"✅ Fixed {image_fixes} missing images from detailed responses")

    def _normalize_lot(self, lot_data: Dict) -> Dict:
        """Normalize a single lot from Goldin API"""
        # Extract lot ID
        lot_id = (
            lot_data.get("lot_id") or
            lot_data.get("id") or
            lot_data.get("lotId") or
            ""
        )

        # Extract title
        title = (
            lot_data.get("title") or
            lot_data.get("name") or
            lot_data.get("lot_title") or
            ""
        )

        # Extract current bid/price (Goldin uses 'current_price')
        current_bid = None
        for key in ['current_price', 'current_bid', 'currentBid', 'high_bid', 'highBid', 'price']:
            if key in lot_data:
                val = lot_data[key]
                if isinstance(val, (int, float)):
                    current_bid = float(val)
                    break
                elif isinstance(val, str):
                    cleaned = re.sub(r'[^0-9.]', '', val)
                    try:
                        current_bid = float(cleaned) if cleaned else None
                        break
                    except:
                        pass

        # Extract image - Goldin uses CloudFront CDN
        # Format: https://d2tt46f3mh26nl.cloudfront.net/public/Lots/{lot_id}/{primary_image_name}@3x
        image_url = None
        primary_image_name = lot_data.get("primary_image_name")
        if primary_image_name and lot_id:
            # Construct the CloudFront URL
            image_url = f"https://d2tt46f3mh26nl.cloudfront.net/public/Lots/{lot_id}/{primary_image_name}@3x"

        # Fallback: check for images array
        if not image_url:
            images = lot_data.get("images") or lot_data.get("lot_images") or []
            if images and isinstance(images, list) and len(images) > 0:
                first_image = images[0]
                if isinstance(first_image, str):
                    image_url = first_image
                elif isinstance(first_image, dict):
                    image_url = (
                        first_image.get("url") or
                        first_image.get("image_url") or
                        first_image.get("src")
                    )

        # Fallback: check direct URL fields
        if not image_url:
            image_url = (
                lot_data.get("image_url") or
                lot_data.get("imageUrl") or
                lot_data.get("image") or
                lot_data.get("thumbnail") or
                lot_data.get("primary_image_url") or
                lot_data.get("main_image")
            )

        # Fallback: try to construct from lot_id if we have a cdn_image_name
        if not image_url and lot_id:
            cdn_image = lot_data.get("cdn_image_name") or lot_data.get("image_name")
            if cdn_image:
                image_url = f"https://d2tt46f3mh26nl.cloudfront.net/public/Lots/{lot_id}/{cdn_image}@3x"

        # Extract category/type
        category = (
            lot_data.get("category") or
            lot_data.get("item_type") or
            lot_data.get("type")
        )

        # Extract end time (Goldin uses 'end_timestamp')
        end_time = None
        end_time_str = (
            lot_data.get("end_timestamp") or
            lot_data.get("end_time") or
            lot_data.get("endTime") or
            lot_data.get("close_time")
        )

        # Parse ISO format timestamp to datetime
        if end_time_str:
            try:
                if isinstance(end_time_str, str):
                    # Handle ISO format like "2025-12-14T03:00:00Z"
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                elif isinstance(end_time_str, datetime):
                    end_time = end_time_str
            except (ValueError, AttributeError):
                # If parsing fails, leave as None
                pass

        # Build URL - Goldin uses /item/ format
        item_url = lot_data.get("url") or ""
        if not item_url:
            meta_slug = lot_data.get("meta_slug")
            # Use /item/ format as shown on Goldin website
            if meta_slug:
                item_url = f"{self.base_url}/item/{meta_slug}"
            elif lot_id:
                # Fallback to lot_id if meta_slug not available
                item_url = f"{self.base_url}/item/{lot_id}"

        # Extract bid count (Goldin uses 'number_of_bids')
        bid_count = 0
        for key in ['number_of_bids', 'bid_count', 'bidCount', 'num_bids']:
            if key in lot_data:
                val = lot_data[key]
                if isinstance(val, (int, float)):
                    bid_count = int(val)
                    break

        # Detect sport from item content
        description = lot_data.get("description")
        sport = detect_sport_from_item(title, description, category).value

        return {
            "external_id": str(lot_id) if lot_id else title[:50],
            "lot_number": lot_data.get("lot_number") or lot_data.get("lotNumber"),
            "cert_number": lot_data.get("cert_number"),  # Grading certification number
            "sub_category": lot_data.get("sub_category"),
            "grading_company": lot_data.get("grading_company"),
            "grade": str(lot_data.get("grade")) if lot_data.get("grade") is not None else None,
            "title": str(title).strip()[:500] if title else "",
            "description": description,
            "category": category,
            "sport": sport,
            "image_url": image_url,
            "current_bid": current_bid,
            "bid_count": bid_count,
            "item_url": item_url,
            "end_time": end_time,
            "status": lot_data.get("status", "active"),
            "raw_data": lot_data,
        }

    def _extract_from_api_response(self, data: Dict) -> List[Dict]:
        """Extract and normalize items from Goldin API response"""
        items = []

        print("\n🔍 Analyzing API response structure...")
        print(f"Top-level type: {type(data)}")

        if isinstance(data, dict):
            print(f"Top-level keys: {list(data.keys())}")

            # Common patterns for auction data
            possible_keys = ['auctions', 'data', 'results', 'items', 'lots']

            for key in possible_keys:
                if key in data:
                    auction_data = data[key]
                    print(f"✅ Found '{key}' in response")

                    if isinstance(auction_data, list):
                        print(f"   Array with {len(auction_data)} items")
                        for item in auction_data:
                            normalized = self._normalize_item(item)
                            if normalized.get('title'):
                                items.append(normalized)
                    elif isinstance(auction_data, dict):
                        # Might be a single auction with lots inside
                        print(f"   Dictionary with keys: {list(auction_data.keys())[:10]}")
                        # Try to find lots within
                        for subkey in ['lots', 'items', 'listings']:
                            if subkey in auction_data:
                                lot_data = auction_data[subkey]
                                if isinstance(lot_data, list):
                                    print(f"   Found {len(lot_data)} items in '{key}.{subkey}'")
                                    for item in lot_data:
                                        normalized = self._normalize_item(item)
                                        if normalized.get('title'):
                                            items.append(normalized)
                    break

            # If no items found yet, try extracting from top level
            if not items and isinstance(data, list):
                print(f"Top level is an array with {len(data)} items")
                for item in data:
                    normalized = self._normalize_item(item)
                    if normalized.get('title'):
                        items.append(normalized)

        elif isinstance(data, list):
            print(f"Response is array with {len(data)} items")
            for item in data:
                normalized = self._normalize_item(item)
                if normalized.get('title'):
                    items.append(normalized)

        return items

    def _extract_from_state(self, state: Dict) -> List[Dict]:
        """Extract auction items from Redux state"""
        items = []

        print("\n🔍 Analyzing Redux state structure...")
        print(f"Top-level keys: {list(state.keys())}")

        # Common places to find auction data in Redux
        paths_to_check = [
            ('shop', 'lots'),
            ('shop', 'items'),
            ('auction', 'lots'),
            ('auction', 'items'),
            ('lots',),
            ('items',),
        ]

        for path in paths_to_check:
            current = state
            try:
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    # Successfully navigated path
                    if isinstance(current, list):
                        print(f"✅ Found array at {' -> '.join(path)}: {len(current)} items")
                        for item in current:
                            if isinstance(item, dict):
                                normalized = self._normalize_item(item)
                                if normalized.get('title'):
                                    items.append(normalized)
                    elif isinstance(current, dict):
                        print(f"✅ Found dict at {' -> '.join(path)}")
                        # Might be keyed by ID
                        for key, value in current.items():
                            if isinstance(value, dict):
                                normalized = self._normalize_item(value)
                                if normalized.get('title'):
                                    items.append(normalized)
            except:
                continue

        return items

    def _normalize_item(self, raw_data: Dict) -> Dict:
        """Normalize item data to our schema"""
        # Extract ID
        lot_id = (
            raw_data.get("id") or
            raw_data.get("lotId") or
            raw_data.get("itemId") or
            ""
        )

        # Extract title
        title = (
            raw_data.get("title") or
            raw_data.get("name") or
            raw_data.get("lotName") or
            ""
        )

        if isinstance(title, str):
            title = title.strip()[:500]

        # Extract price
        current_bid = None
        for key in ['currentBid', 'current_bid', 'price', 'bid', 'highBid']:
            if key in raw_data:
                val = raw_data[key]
                if isinstance(val, (int, float)):
                    current_bid = float(val)
                    break
                elif isinstance(val, str):
                    cleaned = re.sub(r'[^0-9.]', '', val)
                    try:
                        current_bid = float(cleaned) if cleaned else None
                        break
                    except:
                        pass

        # Extract image
        image_url = (
            raw_data.get("imageUrl") or
            raw_data.get("image_url") or
            raw_data.get("image") or
            raw_data.get("thumbnail")
        )

        # Build URL
        item_url = raw_data.get("url") or raw_data.get("link") or ""
        if not item_url and lot_id:
            item_url = f"{self.base_url}/lot/{lot_id}"

        return {
            "external_id": str(lot_id) if lot_id else title[:50],
            "lot_number": raw_data.get("lotNumber"),
            "title": title,
            "description": raw_data.get("description"),
            "category": raw_data.get("category"),
            "image_url": image_url,
            "current_bid": current_bid,
            "bid_count": int(raw_data.get("bidCount", 0) or raw_data.get("bid_count", 0) or 0),
            "item_url": item_url,
            "status": "active",
            "raw_data": raw_data,
        }

    async def get_item_details(self, item_id: str) -> Optional[Dict]:
        """Get details for a specific item"""
        response = await self.client.get(f"{self.base_url}/lot/{item_id}")
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract details...
            return {}
        return None

    async def health_check(self) -> HealthCheckResult:
        """Check if Goldin API is reachable"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://d2l9s2774i83t9.cloudfront.net/api/auctions",
                    headers={
                        'Accept': 'application/json',
                        'Origin': 'https://goldin.co',
                    }
                )
                if response.status_code == 200:
                    return HealthCheckResult(
                        healthy=True,
                        message="Goldin API is reachable",
                        details={"status_code": response.status_code}
                    )
                else:
                    return HealthCheckResult(
                        healthy=False,
                        message=f"Goldin API returned status {response.status_code}",
                        details={"status_code": response.status_code}
                    )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Goldin API unreachable: {str(e)}",
                details={"error": str(e)}
            )

    async def scrape(self, db: AsyncSession, max_items: int = 5000) -> List[Dict]:
        """Main scraping entry point"""
        print("🔍 Fetching items from Goldin...")

        async with GoldinHTTPScraper(db) as scraper:
            items = await scraper.scrape_auction_items(max_items=max_items)

            # Limit to max_items (should already be limited, but ensure)
            items = items[:max_items]

            # Create/update Auction records for each unique auction_id
            auction_map = {}

            # Get unique auction IDs from items
            unique_auction_ids = set()
            for item in items:
                goldin_auction_id = item.get('raw_data', {}).get('auction_id')
                if goldin_auction_id:
                    unique_auction_ids.add(goldin_auction_id)

            print(f"\n📦 Creating/updating {len(unique_auction_ids)} auction records...")

            # Create or get auction records
            for goldin_auction_id in unique_auction_ids:
                result = await db.execute(
                    select(Auction).where(
                        Auction.auction_house == 'goldin',
                        Auction.external_id == goldin_auction_id
                    )
                )
                auction = result.scalar_one_or_none()

                if not auction:
                    auction = Auction(
                        auction_house='goldin',
                        external_id=goldin_auction_id,
                        title=f"Goldin Auction {goldin_auction_id[:8]}...",
                        status='active'
                    )
                    db.add(auction)
                    await db.flush()

                auction_map[goldin_auction_id] = auction.id

            await db.commit()
            print(f"✅ Created/updated {len(auction_map)} auctions")

            # Associate items with their auctions
            for item in items:
                goldin_auction_id = item.get('raw_data', {}).get('auction_id')
                if goldin_auction_id and goldin_auction_id in auction_map:
                    item['auction_id'] = auction_map[goldin_auction_id]

            # Batch upsert: fetch all existing rows up front (avoids N+1 SELECTs)
            print(f"\n💾 Saving {len(items)} items to database...")

            # De-duplicate items by external_id (keep last occurrence), since the
            # source can return the same lot more than once across pages.
            items_by_external_id = {item["external_id"]: item for item in items}
            unique_items = list(items_by_external_id.values())
            external_ids = list(items_by_external_id.keys())

            # Fetch existing rows in chunks to keep IN() clauses bounded.
            existing_items = {}
            chunk_size = 1000
            for chunk_start in range(0, len(external_ids), chunk_size):
                id_chunk = external_ids[chunk_start:chunk_start + chunk_size]
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == "goldin",
                        AuctionItem.external_id.in_(id_chunk)
                    )
                )
                for existing in result.scalars().all():
                    existing_items[existing.external_id] = existing

            print(f"   ... {len(unique_items)} unique items ({len(existing_items)} existing)")

            new_count = 0
            update_count = 0
            for item in unique_items:
                existing_item = existing_items.get(item["external_id"])

                if existing_item:
                    for key, value in item.items():
                        if key not in ['external_id', 'auction_house']:
                            setattr(existing_item, key, value)
                    existing_item.updated_at = datetime.utcnow()
                    update_count += 1
                else:
                    new_item = AuctionItem(
                        auction_house="goldin",
                        **item
                    )
                    db.add(new_item)
                    new_count += 1

            await db.commit()
            print(f"✅ Saved {len(unique_items)} items to database ({new_count} new, {update_count} updated)")

            # Time-based stale marking: the Goldin scraper is capped (max_items)
            # and does NOT pull the complete live set, so we must NOT mark
            # "not seen this run" items as ended (that would wrongly end live
            # lots we simply didn't fetch). Instead, only mark items whose
            # end_time has already passed.
            now = datetime.utcnow()  # naive UTC to match how end_time is stored
            ended_result = await db.execute(
                text(
                    "UPDATE auction_items SET status = 'Ended' "
                    "WHERE auction_house = 'goldin' "
                    "AND end_time < :now "
                    "AND status != 'Ended'"
                ),
                {"now": now},
            )
            await db.commit()
            ended_count = ended_result.rowcount or 0
            print(f"⏰ Marked {ended_count} past-end-time items as Ended (time-based)")

            # Count items with grading data
            graded_items = [item for item in items if item.get('grading_company')]
            print(f"   Items with grading data: {len(graded_items)}")

            return items


async def run_goldin_http_scraper(db):
    """Run the HTTP scraper"""
    from app.models import Auction
    from sqlalchemy import select

    async with GoldinHTTPScraper(db) as scraper:
        items = await scraper.scrape_auction_items()

        # First, create/update Auction records for each unique auction_id
        auction_map = {}  # Map Goldin auction_id -> database auction.id

        # Get unique auction IDs from items
        unique_auction_ids = set()
        for item in items:
            goldin_auction_id = item.get('raw_data', {}).get('auction_id')
            if goldin_auction_id:
                unique_auction_ids.add(goldin_auction_id)

        print(f"\n📦 Creating/updating {len(unique_auction_ids)} auction records...")

        # Create or get auction records
        for goldin_auction_id in unique_auction_ids:
            # Check if auction exists
            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == 'goldin',
                    Auction.external_id == goldin_auction_id
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                # Create new auction
                auction = Auction(
                    auction_house='goldin',
                    external_id=goldin_auction_id,
                    title=f"Goldin Auction {goldin_auction_id[:8]}...",
                    status='active'
                )
                db.add(auction)
                await db.flush()  # Get the ID

            auction_map[goldin_auction_id] = auction.id

        await db.commit()
        print(f"✅ Created/updated {len(auction_map)} auctions")

        # Now associate items with their auctions
        for item in items:
            goldin_auction_id = item.get('raw_data', {}).get('auction_id')
            if goldin_auction_id and goldin_auction_id in auction_map:
                item['auction_id'] = auction_map[goldin_auction_id]

        # Save items
        await scraper.save_to_database(items)
        return items


if __name__ == "__main__":
    """Run the scraper directly"""
    import sys
    sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

    from app.database import get_db, init_db
    # Import models so they're registered with Base.metadata
    from app.models import auction  # noqa: F401

    async def main():
        # Initialize database
        await init_db()

        # Get database session
        async for db in get_db():
            try:
                items = await run_goldin_http_scraper(db)
                print(f"\n✅ Successfully scraped {len(items)} items")
            finally:
                await db.close()
            break

    asyncio.run(main())
