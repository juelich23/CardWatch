"""
Try to find and use Goldin's direct bid API
Based on their API pattern: cloudfront.net/api/<service>
"""
import asyncio
import httpx
import json
import sqlite3
import sys
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from app.services.encryption import get_encryption_service

# Get session data
conn = sqlite3.connect('auction_data.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT us.encrypted_browser_state, us.encryption_iv
    FROM user_sessions us
    JOIN auction_house_credentials ahc ON us.credential_id = ahc.id
    WHERE ahc.auction_house = 'goldin' AND us.is_active = 1
    ORDER BY us.id DESC LIMIT 1
""")
row = cursor.fetchone()
conn.close()

encryption = get_encryption_service()
session_json = encryption.decrypt(row[0], row[1])
session_data = json.loads(session_json)

# Get the idToken
local_storage = session_data.get('localStorage', {})
id_token = None
for key, value in local_storage.items():
    if 'idToken' in key:
        id_token = value
        break

print(f"ID Token found: {'Yes' if id_token else 'No'}")

# Get item info
conn = sqlite3.connect('auction_data.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT external_id, item_url, title, current_bid FROM auction_items
    WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid > 0
    ORDER BY current_bid ASC LIMIT 1
""")
row = cursor.fetchone()
conn.close()

external_id, item_url, title, current_bid = row
bid_amount = int(current_bid) + 10

# Extract lot_id and auction_id from external_id
# external_id format: 202509-2317-5631-ae50e730-df16-4782-b1ab-d15a3edc8113
lot_id = external_id

print(f"\nItem: {title[:50]}...")
print(f"Lot ID: {lot_id}")
print(f"Current bid: ${current_bid}")
print(f"Our bid: ${bid_amount}")

# Try various possible bid endpoints
async def try_bid_endpoints():
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            'Authorization': id_token,
            'Content-Type': 'application/json',
            'Origin': 'https://goldin.co',
            'Referer': item_url,
        }

        # Known CloudFront endpoints from interception:
        # d1wu47wucybvr3.cloudfront.net/api/lots
        # d48cwzgutl593.cloudfront.net/api/bidding/lots
        # d2b0m2pytsm6xz.cloudfront.net/api/bid_history
        # dgzhctp9iogel.cloudfront.net/api/watchlist
        # d2l9s2774i83t9.cloudfront.net/api/auctions
        # d1ltxmuqtnhgf5.cloudfront.net/api/cash-account
        # d2tsdfi87wvj8x.cloudfront.net/api/get_all_cards
        # d12nbv15dy6dwk.cloudfront.net/api/user_account_badges

        # Try possible bid endpoints
        bid_endpoints = [
            # Common patterns
            ("https://d48cwzgutl593.cloudfront.net/api/bid", "POST"),
            ("https://d48cwzgutl593.cloudfront.net/api/bids", "POST"),
            ("https://d48cwzgutl593.cloudfront.net/api/place_bid", "POST"),
            ("https://d48cwzgutl593.cloudfront.net/api/bidding/bid", "POST"),
            ("https://d48cwzgutl593.cloudfront.net/api/bidding/place", "POST"),
            ("https://d2b0m2pytsm6xz.cloudfront.net/api/bid", "POST"),
            ("https://d2b0m2pytsm6xz.cloudfront.net/api/place_bid", "POST"),
            # Try other CloudFronts
            ("https://d1wu47wucybvr3.cloudfront.net/api/bid", "POST"),
            ("https://dgzhctp9iogel.cloudfront.net/api/bid", "POST"),
        ]

        # Common bid payloads to try
        bid_payloads = [
            {"lot_id": lot_id, "amount": bid_amount},
            {"lot_id": lot_id, "bid_amount": bid_amount},
            {"lotId": lot_id, "amount": bid_amount},
            {"lotId": lot_id, "bidAmount": bid_amount},
            {"lot_id": lot_id, "max_bid": bid_amount},
            {"lot_id": lot_id, "bid": bid_amount},
        ]

        print("\n=== Testing bid endpoints ===")

        for endpoint, method in bid_endpoints:
            for payload in bid_payloads[:1]:  # Just try first payload for each endpoint
                try:
                    print(f"\nTrying: {endpoint}")
                    print(f"Payload: {payload}")

                    response = await client.post(endpoint, json=payload, headers=headers)
                    print(f"Status: {response.status_code}")
                    print(f"Response: {response.text[:500]}")

                    if response.status_code == 200:
                        print("*** POTENTIAL SUCCESS! ***")

                except Exception as e:
                    print(f"Error: {e}")

        # Also try to get the bidding endpoint from the lot info
        print("\n=== Getting lot bidding info ===")
        try:
            # This endpoint returns bidding info
            slug = item_url.split('/')[-1]
            response = await client.get(
                f"https://d48cwzgutl593.cloudfront.net/api/bidding/lots?slug={slug}",
                headers=headers
            )
            print(f"Bidding lot info: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response (first 1000 chars): {json.dumps(data)[:1000]}")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(try_bid_endpoints())
