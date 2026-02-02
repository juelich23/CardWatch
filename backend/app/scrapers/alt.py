#!/usr/bin/env python3
"""
Alt.xyz Scraper
Fetches auction items from Alt.xyz using their Typesense search API
"""

import asyncio
import httpx
import re
import base64
import json
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult, retry_async
from app.utils.sport_detection import detect_sport_from_item


class AltScraper:
    """Scraper for Alt.xyz liquid auctions"""

    def __init__(self):
        self.typesense_host = "tlzfv6xaq81nhsbyp.a1.typesense.net"
        self.collection = "production_universal_search"
        self.base_url = "https://app.alt.xyz"
        self.auction_house_name = "alt"

    def _get_search_url(self, api_key: str) -> str:
        """Build the Typesense multi_search URL"""
        return (
            f"https://{self.typesense_host}/multi_search"
            f"?collection={self.collection}"
            f"&use_cache=true"
            f"&x-typesense-api-key={api_key}"
        )

    @retry_async(max_retries=3, delay=1.0)
    async def fetch_api_key(self, client: httpx.AsyncClient) -> str:
        """
        Fetch a fresh Typesense API key from Alt.xyz.
        The key is embedded in the page's JavaScript.
        """
        # For now, we'll use a long-lived approach by fetching the main page
        # and extracting the key from the JavaScript bundle or config
        # This is a simplified approach - in production you might need
        # to extract from the JS bundle dynamically

        # Try to get the key from their public search endpoint
        # Alt.xyz uses scoped keys that are embedded in their frontend

        # Default to using a placeholder - the actual key should be
        # fetched from the frontend or passed in
        raise NotImplementedError(
            "API key fetch not implemented - pass key via environment variable ALT_TYPESENSE_KEY"
        )

    @retry_async(max_retries=3, delay=1.0)
    async def fetch_items(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        page: int = 1,
        per_page: int = 100,
        sort_by: str = "price_desc",
    ) -> Dict:
        """Fetch auction items from Typesense API"""
        url = self._get_search_url(api_key)

        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "text/plain",
            "origin": self.base_url,
            "referer": f"{self.base_url}/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

        # Build filter to get active Alt auctions
        payload = {
            "searches": [
                {
                    "q": "",
                    "preset": sort_by,
                    "filter_by": "listingType:[AUCTION,EXTERNAL_AUCTION]&&auctionHouse:[Alt]&&showResult:true",
                    "per_page": per_page,
                    "page": page,
                }
            ]
        }

        response = await client.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def extract_grading_info(self, doc: Dict) -> Dict:
        """Extract grading information from document"""
        return {
            "grading_company": doc.get("gradingCompany"),
            "grade": doc.get("grade"),
            "cert_number": None,  # Alt doesn't provide cert numbers in search
        }

    def map_category_to_sport(self, category: str) -> Optional[str]:
        """Map Alt.xyz category to sport"""
        category_map = {
            "BASKETBALL_CARDS": "BASKETBALL",
            "FOOTBALL_CARDS": "FOOTBALL",
            "BASEBALL_CARDS": "BASEBALL",
            "HOCKEY_CARDS": "HOCKEY",
            "SOCCER_CARDS": "SOCCER",
            "MAGIC_CARDS": "TCG",
            "POKEMON_CARDS": "TCG",
            "ONE_PIECE_CARDS": "TCG",
            "YUGIOH_CARDS": "TCG",
        }
        return category_map.get(category)

    def normalize_item(self, doc: Dict) -> Dict:
        """Convert Alt.xyz item to our standard format"""
        # Get title - prefer itemName (includes grading) over name
        title = doc.get("itemName") or doc.get("name", "")

        # Extract grading information
        grading_info = self.extract_grading_info(doc)

        # Get price
        current_bid = doc.get("price", 0)
        if not current_bid and doc.get("priceCents"):
            current_bid = doc["priceCents"] / 100

        # Get end time
        end_time = None
        if doc.get("expiresAt"):
            try:
                end_time_str = doc["expiresAt"]
                # Parse ISO format with timezone
                end_time = datetime.fromisoformat(end_time_str.replace("+00:00", ""))
            except Exception:
                pass

        # Get image URL (prefer FRONT image)
        image_url = None
        images = doc.get("images", [])
        if images:
            front_images = [img for img in images if img.get("position") == "FRONT"]
            if front_images:
                image_url = front_images[0].get("url")
            elif images:
                image_url = images[0].get("url")

        # Build item URL
        listing_id = doc.get("listingId") or doc.get("id")
        item_url = f"{self.base_url}/liquid-auctions/select-listing?ids={listing_id}" if listing_id else None

        # Map category to sport
        category = doc.get("category")
        sport = self.map_category_to_sport(category)

        # If no sport from category, try detection
        if not sport:
            detected = detect_sport_from_item(
                title,
                doc.get("subject", ""),
                category
            )
            sport = detected.value if detected else None

        # Extract human-readable category
        readable_category = None
        if category:
            # Convert BASKETBALL_CARDS -> Basketball
            readable_category = category.replace("_CARDS", "").replace("_", " ").title()

        return {
            "external_id": listing_id,
            "lot_number": None,
            "cert_number": grading_info["cert_number"],
            "grading_company": grading_info["grading_company"],
            "grade": grading_info["grade"],
            "title": title[:500] if title else "",
            "description": doc.get("subtitle"),
            "category": readable_category,
            "sport": sport,
            "image_url": image_url,
            "current_bid": current_bid,
            "starting_bid": None,
            "bid_count": doc.get("bidCount", 0),
            "end_time": end_time,
            "status": "Live" if not doc.get("hasAuctionEnded") else "Ended",
            "item_url": item_url,
            "raw_data": {
                "alt_value": doc.get("altValue"),
                "alt_value_confidence": doc.get("altValueConfidenceMetric"),
                "year": doc.get("year"),
                "brand": doc.get("brand"),
                "variety": doc.get("variety"),
                "subject": doc.get("subject"),
                "serial": doc.get("serial"),
                "print_run": doc.get("printRun"),
                "auction_name": doc.get("auctionName"),
                "watch_count": doc.get("watchCount"),
            },
        }

    async def scrape(self, db: AsyncSession, api_key: str, max_items: int = 10000) -> List[Dict]:
        """
        Main scraping function - fetches all auction items from Alt.xyz

        Args:
            db: Database session
            api_key: Typesense API key (scoped key from Alt.xyz frontend)
            max_items: Maximum number of items to fetch
        """
        print(f"[ALT] Starting scrape (max_items={max_items})", flush=True)

        all_items = []
        seen_ids = set()

        async with httpx.AsyncClient() as client:
            page = 1
            per_page = 100  # Typesense default max

            while len(all_items) < max_items:
                print(f"[ALT] Fetching page {page}...", flush=True)

                try:
                    response = await self.fetch_items(
                        client, api_key, page=page, per_page=per_page
                    )
                except Exception as e:
                    print(f"[ALT] Error fetching page {page}: {e}", flush=True)
                    break

                results = response.get("results", [])
                if not results:
                    break

                result = results[0]
                hits = result.get("hits", [])
                total_found = result.get("found", 0)

                if page == 1:
                    print(f"[ALT] Total items available: {total_found}", flush=True)

                if not hits:
                    break

                # Process hits
                new_count = 0
                for hit in hits:
                    doc = hit.get("document", {})
                    listing_id = doc.get("listingId") or doc.get("id")

                    if listing_id and listing_id not in seen_ids:
                        seen_ids.add(listing_id)
                        normalized = self.normalize_item(doc)
                        all_items.append(normalized)
                        new_count += 1

                print(f"[ALT] Page {page}: {len(hits)} items, {new_count} new (total: {len(all_items)})", flush=True)

                # Check if we've reached the end
                if len(hits) < per_page or len(all_items) >= total_found:
                    break

                page += 1

                # Small delay between pages
                await asyncio.sleep(0.2)

            print(f"[ALT] Fetched {len(all_items)} unique items", flush=True)

            # Create or update auction record
            print("[ALT] Creating/updating auction record...", flush=True)
            auction_external_id = "alt-liquid-auctions"

            result = await db.execute(
                select(Auction).where(
                    Auction.auction_house == self.auction_house_name,
                    Auction.external_id == auction_external_id,
                )
            )
            auction = result.scalar_one_or_none()

            if not auction:
                auction = Auction(
                    auction_house=self.auction_house_name,
                    external_id=auction_external_id,
                    title="Alt Liquid Auctions",
                    status="active",
                )
                db.add(auction)
                await db.flush()

            print(f"[ALT] Auction ID: {auction.id}", flush=True)

            # Save items to database in batches
            print(f"[ALT] Saving {len(all_items)} items to database...", flush=True)
            batch_size = 50
            processed = 0

            for item_data in all_items:
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == self.auction_house_name,
                        AuctionItem.external_id == item_data["external_id"],
                    )
                )
                existing_item = result.scalar_one_or_none()

                if existing_item:
                    # Update existing item
                    for key, value in item_data.items():
                        if key not in ["external_id", "auction_house"]:
                            setattr(existing_item, key, value)
                    existing_item.updated_at = datetime.utcnow()
                else:
                    # Create new item
                    item = AuctionItem(
                        auction_id=auction.id,
                        auction_house=self.auction_house_name,
                        **item_data,
                    )
                    db.add(item)

                processed += 1

                # Commit in batches
                if processed % batch_size == 0:
                    await db.commit()
                    print(f"[ALT] Saved {processed}/{len(all_items)} items", flush=True)
                    await asyncio.sleep(0.1)

            # Final commit
            await db.commit()
            print(f"[ALT] Saved {len(all_items)} items to database", flush=True)

            return all_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Alt.xyz is reachable"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self.base_url}/liquid-auctions",
                    follow_redirects=True,
                )
                if response.status_code == 200:
                    return HealthCheckResult(
                        healthy=True,
                        message="Alt.xyz is reachable",
                        details={"status_code": response.status_code},
                    )
                return HealthCheckResult(
                    healthy=False,
                    message=f"Alt.xyz returned status {response.status_code}",
                    details={"status_code": response.status_code},
                )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Alt.xyz unreachable: {str(e)}",
                details={"error": str(e)},
            )


async def main():
    """Entry point for running the scraper manually"""
    import os
    from app.database import init_db, get_db

    # Get API key from environment
    api_key = os.getenv("ALT_TYPESENSE_KEY")
    if not api_key:
        print("ERROR: ALT_TYPESENSE_KEY environment variable not set")
        print("Get the key from browser DevTools Network tab when loading Alt.xyz auctions page")
        return

    # Initialize database
    await init_db()

    scraper = AltScraper()

    # Get database session
    async for db in get_db():
        items = await scraper.scrape(db, api_key=api_key, max_items=1000)

        print(f"\nScraping complete!")
        print(f"  Total items: {len(items)}")

        # Count by sport
        sports = {}
        for item in items:
            sport = item.get("sport") or "Unknown"
            sports[sport] = sports.get(sport, 0) + 1

        print("  By sport:")
        for sport, count in sorted(sports.items(), key=lambda x: -x[1]):
            print(f"    {sport}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
