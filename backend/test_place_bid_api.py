"""
Test the place_bid endpoint with different payload formats
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

# Need auction_id - let's get it from the API
async def get_lot_info_and_bid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            'Authorization': id_token,
            'Content-Type': 'application/json',
            'Origin': 'https://goldin.co',
            'Referer': item_url,
        }

        # First get lot info to get auction_id
        slug = item_url.split('/')[-1]
        response = await client.get(
            f"https://d48cwzgutl593.cloudfront.net/api/bidding/lots?slug={slug}",
            headers=headers
        )
        lot_data = response.json()[0]

        auction_id = lot_data.get('auction_id')
        current = lot_data.get('current_bid', current_bid)
        lot_num = lot_data.get('lot_number')

        print(f"Lot ID: {lot_id}")
        print(f"Auction ID: {auction_id}")
        print(f"Current bid: ${current}")
        print(f"Lot number: {lot_num}")
        print(f"Our bid: ${bid_amount}")

        # Try various payload formats for place_bid
        endpoint = "https://d2b0m2pytsm6xz.cloudfront.net/api/place_bid"

        payloads = [
            # Based on bid_history API format
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "bid_amount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "max_bid": bid_amount},
            {"lotId": lot_id, "auctionId": auction_id, "amount": bid_amount},
            {"lotId": lot_id, "auctionId": auction_id, "bidAmount": bid_amount},
            {"lotId": lot_id, "auctionId": auction_id, "maxBid": bid_amount},
            # Try with bid field
            {"lot_id": lot_id, "auction_id": auction_id, "bid": bid_amount},
            # Try with current_bid reference
            {"lot_id": lot_id, "auction_id": auction_id, "new_bid": bid_amount},
            # Try snake_case
            {"lot_id": lot_id, "auction_id": auction_id, "bid_amount": bid_amount, "max_bid": bid_amount},
        ]

        print(f"\n=== Testing place_bid endpoint ===")
        print(f"Endpoint: {endpoint}")

        for payload in payloads:
            try:
                print(f"\nPayload: {json.dumps(payload)}")
                response = await client.post(endpoint, json=payload, headers=headers)
                print(f"Status: {response.status_code}")
                resp_text = response.text
                print(f"Response: {resp_text[:500]}")

                # Check if it worked
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('statusCode') == 200:
                            print("*** SUCCESS! ***")
                            print(f"Full response: {json.dumps(data, indent=2)}")
                            return data
                        elif data.get('statusCode') != 500:
                            print(f"*** Non-500 response: {data.get('statusCode')} ***")
                    except:
                        pass

            except Exception as e:
                print(f"Error: {e}")

        # Also try other potential endpoints
        print("\n=== Trying other potential endpoints ===")
        other_endpoints = [
            "https://d48cwzgutl593.cloudfront.net/api/bidding/place_bid",
            "https://d48cwzgutl593.cloudfront.net/api/place_bid",
        ]

        for ep in other_endpoints:
            payload = {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount}
            try:
                print(f"\nEndpoint: {ep}")
                print(f"Payload: {json.dumps(payload)}")
                response = await client.post(ep, json=payload, headers=headers)
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text[:500]}")
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(get_lot_info_and_bid())
