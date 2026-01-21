"""
Test place_bid API with company_id header
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
lot_id = external_id
bid_amount = int(current_bid) + 10

print(f"Item: {title[:50]}...")
print(f"Lot ID: {lot_id}")
print(f"Current bid: ${current_bid}")
print(f"Our bid: ${bid_amount}")

async def test_with_company_id():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Headers from intercepted request
        headers = {
            'accept': 'application/json, text/plain, */*',
            'authorization': id_token,
            'content-type': 'application/json',
            'origin': 'https://goldin.co',
            'referer': item_url,
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'company_id': '4d802a9f-922c-46bd-83c7-45f18f452f67',
        }

        # Get lot info first
        slug = item_url.split('/')[-1]
        response = await client.get(
            f"https://d48cwzgutl593.cloudfront.net/api/bidding/lots?slug={slug}",
            headers=headers
        )
        lot_data = response.json()
        lot = lot_data[0] if isinstance(lot_data, list) else lot_data
        auction_id = lot.get('auction_id')

        print(f"Auction ID: {auction_id}")

        # Test payloads with company_id header
        endpoint = "https://d2b0m2pytsm6xz.cloudfront.net/api/place_bid"

        payloads = [
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "bid_amount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "max_bid": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "user_max_bid": bid_amount},
            {"lotId": lot_id, "auctionId": auction_id, "amount": bid_amount},

            # With company_id in payload
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount, "company_id": "4d802a9f-922c-46bd-83c7-45f18f452f67"},

            # Different amount field names
            {"lot_id": lot_id, "auction_id": auction_id, "new_max_bid": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "max_bid_amount": bid_amount},
        ]

        print(f"\n=== Testing with company_id header ===")

        for i, payload in enumerate(payloads):
            try:
                print(f"\n{i+1}. {json.dumps(payload)[:100]}")
                response = await client.post(endpoint, json=payload, headers=headers)

                resp_data = response.json()
                status_code = resp_data.get('statusCode', response.status_code)
                body = resp_data.get('body', resp_data)

                if status_code == 200:
                    print(f"   *** SUCCESS! *** Response: {json.dumps(body)[:200]}")
                    return body
                elif status_code != 500:
                    print(f"   Status {status_code}: {json.dumps(body)[:200]}")
                else:
                    response_type = body.get('responseType', '') if isinstance(body, dict) else str(body)
                    print(f"   500 error: {response_type}")

            except Exception as e:
                print(f"   Error: {e}")

        # Also try other potential endpoints
        print(f"\n=== Trying other endpoints ===")

        other_endpoints = [
            "https://d48cwzgutl593.cloudfront.net/api/bidding/bid",
            "https://d48cwzgutl593.cloudfront.net/api/bidding/place_bid",
            "https://d48cwzgutl593.cloudfront.net/api/bid",
            "https://d2b0m2pytsm6xz.cloudfront.net/api/bid",
            "https://d2b0m2pytsm6xz.cloudfront.net/api/submit_bid",
        ]

        payload = {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount}

        for ep in other_endpoints:
            try:
                print(f"\n{ep}")
                response = await client.post(ep, json=payload, headers=headers)
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text[:300]}")
            except Exception as e:
                print(f"   Error: {e}")

asyncio.run(test_with_company_id())
