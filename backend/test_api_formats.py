"""
Test different API payload formats more systematically
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

print(f"ID Token length: {len(id_token) if id_token else 0}")

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

async def test_api():
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            'Authorization': id_token,
            'Content-Type': 'application/json',
            'Origin': 'https://goldin.co',
            'Referer': item_url,
        }

        # First get lot info to see all available fields
        slug = item_url.split('/')[-1]
        print(f"\n=== Getting lot info for slug: {slug} ===")

        # Get lot data from bidding endpoint
        response = await client.get(
            f"https://d48cwzgutl593.cloudfront.net/api/bidding/lots?slug={slug}",
            headers=headers
        )
        print(f"Bidding lots status: {response.status_code}")

        if response.status_code == 200:
            lot_data = response.json()
            print(f"\n=== LOT DATA (from bidding/lots) ===")
            print(json.dumps(lot_data, indent=2)[:2000])

            if lot_data:
                lot = lot_data[0] if isinstance(lot_data, list) else lot_data
                auction_id = lot.get('auction_id')
                lot_number = lot.get('lot_number')
                current = lot.get('current_bid', current_bid)
                min_bid = lot.get('min_bid')
                company_id = lot.get('company_id')
                user_id = lot.get('user_id')

                print(f"\nExtracted fields:")
                print(f"  auction_id: {auction_id}")
                print(f"  lot_number: {lot_number}")
                print(f"  current_bid: {current}")
                print(f"  min_bid: {min_bid}")
                print(f"  company_id: {company_id}")
                print(f"  user_id (from lot): {user_id}")

        # Also get from the lots endpoint
        print(f"\n=== Getting from d1wu47wucybvr3 lots ===")
        response = await client.post(
            "https://d1wu47wucybvr3.cloudfront.net/api/lots",
            json={"queryType": "Search", "slug": [slug]},
            headers=headers
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:1500]}")

            if data.get('body', {}).get('lots'):
                lot2 = data['body']['lots'][0]
                print(f"\nAdditional fields from lots API:")
                for key in ['auction_id', 'company_id', 'lot_id', 'id', 'item_id', 'lot_number', 'user_id']:
                    if key in lot2:
                        print(f"  {key}: {lot2[key]}")

        # Get user info
        print(f"\n=== Getting user account info ===")
        response = await client.get(
            "https://d12nbv15dy6dwk.cloudfront.net/api/user_account_badges",
            headers=headers
        )
        print(f"User badges status: {response.status_code}")
        if response.status_code == 200:
            user_data = response.json()
            print(f"User data: {json.dumps(user_data, indent=2)[:500]}")

        # Try cash account for user_id
        print(f"\n=== Getting cash account ===")
        response = await client.get(
            "https://d1ltxmuqtnhgf5.cloudfront.net/api/cash-account",
            headers=headers
        )
        print(f"Cash account status: {response.status_code}")
        if response.status_code == 200:
            cash_data = response.json()
            print(f"Cash data: {json.dumps(cash_data, indent=2)[:500]}")

        # Now try different payload formats for place_bid
        print(f"\n\n=== TESTING PLACE_BID PAYLOADS ===")

        # Get the fresh data
        response = await client.get(
            f"https://d48cwzgutl593.cloudfront.net/api/bidding/lots?slug={slug}",
            headers=headers
        )
        lot_data = response.json()
        lot = lot_data[0] if isinstance(lot_data, list) else lot_data

        auction_id = lot.get('auction_id')
        min_bid = lot.get('min_bid', int(current_bid) + 2)
        lot_number = lot.get('lot_number')

        print(f"\nUsing:")
        print(f"  lot_id: {lot_id}")
        print(f"  auction_id: {auction_id}")
        print(f"  min_bid: {min_bid}")
        print(f"  bid_amount: {bid_amount}")

        endpoint = "https://d2b0m2pytsm6xz.cloudfront.net/api/place_bid"

        # Try many different payload structures
        payloads = [
            # Standard formats
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "bid": bid_amount},

            # With user_max_bid field (common in auction APIs)
            {"lot_id": lot_id, "auction_id": auction_id, "user_max_bid": bid_amount},

            # Nested structures
            {"lot_id": lot_id, "auction_id": auction_id, "bidData": {"amount": bid_amount}},
            {"lot": {"id": lot_id, "auction_id": auction_id}, "amount": bid_amount},

            # With lot_number
            {"lot_id": lot_id, "auction_id": auction_id, "lot_number": lot_number, "amount": bid_amount},

            # Cents instead of dollars
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount * 100},

            # String amount
            {"lot_id": lot_id, "auction_id": auction_id, "amount": str(bid_amount)},

            # Float amount
            {"lot_id": lot_id, "auction_id": auction_id, "amount": float(bid_amount)},

            # Different field names for amount
            {"lot_id": lot_id, "auction_id": auction_id, "bidAmount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "maxBid": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "max_bid_amount": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "bid_value": bid_amount},
            {"lot_id": lot_id, "auction_id": auction_id, "price": bid_amount},

            # CamelCase for all fields
            {"lotId": lot_id, "auctionId": auction_id, "amount": bid_amount},
            {"lotId": lot_id, "auctionId": auction_id, "bid": bid_amount},
            {"lotId": lot_id, "auctionId": auction_id, "userMaxBid": bid_amount},

            # With action type
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount, "action": "place_bid"},
            {"lot_id": lot_id, "auction_id": auction_id, "amount": bid_amount, "type": "bid"},

            # Just lot_id (maybe auction_id inferred)
            {"lot_id": lot_id, "amount": bid_amount},
            {"lotId": lot_id, "amount": bid_amount},
        ]

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
                    # 500 error - payload likely wrong
                    response_type = body.get('responseType', '') if isinstance(body, dict) else str(body)
                    print(f"   500 error: {response_type}")

            except Exception as e:
                print(f"   Error: {e}")

        print("\n\nNo successful payload found. The bid API might require MQTT.")

asyncio.run(test_api())
