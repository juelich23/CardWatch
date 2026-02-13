#!/usr/bin/env python3
"""
Run eBay scraper locally and upload results to production API.
Usage: python scrape_ebay_local.py [--max-items 500]
"""
import asyncio
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx


PROD_API = "https://cardwatch-api-production.up.railway.app"


async def main():
    max_items = 500
    if "--max-items" in sys.argv:
        idx = sys.argv.index("--max-items")
        max_items = int(sys.argv[idx + 1])

    # Step 1: Login to get a token
    print("Logging in...")
    email = input("Email: ").strip()
    import getpass
    password = getpass.getpass("Password: ")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{PROD_API}/auth/login", json={
            "email": email,
            "password": password,
        })
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            return
        token = resp.json()["access_token"]
        print("Logged in!")

    # Step 2: Run the scraper locally (uses SQLite, we just want the normalized items)
    print(f"\nScraping eBay (max_items={max_items})...")

    from app.scrapers.ebay import EbayScraper, _parse_time_left, _parse_price, _parse_bid_count, _extract_grading_info, _extract_category, SEARCH_CONFIGS, EXTRACT_ITEMS_JS
    from app.utils.sport_detection import detect_sport_from_item

    scraper = EbayScraper()
    all_items = {}

    try:
        for config in SEARCH_CONFIGS:
            if len(all_items) >= max_items:
                break

            query = config["query"]
            category = config.get("category")
            print(f"  Searching: '{query}' (cat={category})")

            page_num = 1
            max_pages = 3
            consecutive_empty = 0

            while page_num <= max_pages and len(all_items) < max_items:
                url = scraper._build_search_url(query, category, page_num)
                raw_items = await scraper._fetch_search_page(url)

                if not raw_items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    page_num += 1
                    await asyncio.sleep(3)
                    continue

                consecutive_empty = 0
                new_count = 0
                for raw in raw_items:
                    item = scraper._normalize_item(raw)
                    if item and item["external_id"] not in all_items:
                        all_items[item["external_id"]] = item
                        new_count += 1

                print(f"    Page {page_num}: {len(raw_items)} found, {new_count} new (total: {len(all_items)})")

                if new_count == 0:
                    break
                page_num += 1
                await asyncio.sleep(3)
    finally:
        await scraper._close_browser()

    items_list = list(all_items.values())[:max_items]
    print(f"\nScraped {len(items_list)} items")

    if not items_list:
        print("No items found!")
        return

    # Step 3: Upload to production
    print(f"\nUploading {len(items_list)} items to production...")

    # Convert datetime objects to ISO strings for JSON
    upload_items = []
    for item in items_list:
        upload = {**item}
        if upload.get("end_time"):
            upload["end_time"] = upload["end_time"].isoformat()
        # Remove raw_data (not in upload schema)
        upload.pop("raw_data", None)
        upload_items.append(upload)

    # Upload in batches
    batch_size = 100
    total_new = 0
    total_updated = 0
    async with httpx.AsyncClient(timeout=60) as client:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        for i in range(0, len(upload_items), batch_size):
            batch = upload_items[i:i + batch_size]
            resp = await client.post(
                f"{PROD_API}/api/bidding/upload-ebay-items",
                json=batch,
                headers=headers,
            )
            if resp.status_code == 200:
                result = resp.json()
                print(f"  Batch {i // batch_size + 1}: {result['message']}")
            else:
                print(f"  Batch {i // batch_size + 1} FAILED: {resp.status_code} {resp.text}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
