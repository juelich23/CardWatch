"""
Test the fast bidding implementation
"""
import asyncio
import time
import sys
import json
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

import sqlite3
from app.services.encryption import get_encryption_service
from app.services.auction_auth.browser_manager import get_browser_manager

async def test_fast_bid():
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

    # Get test item
    cursor.execute("""
        SELECT id, item_url, title, current_bid FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid > 0
        ORDER BY current_bid ASC LIMIT 1
    """)
    item_row = cursor.fetchone()
    conn.close()

    if not row:
        print("No active Goldin session found. Please login first.")
        return

    if not item_row:
        print("No live auction items found.")
        return

    encryption = get_encryption_service()
    session_json = encryption.decrypt(row[0], row[1])
    session_data = json.loads(session_json)

    item_id, item_url, title, current_bid = item_row
    bid_amount = int(current_bid) + 2

    print(f"=== Fast Bidding Test ===")
    print(f"Item: {title[:60]}...")
    print(f"Current bid: ${current_bid}")
    print(f"Our bid: ${bid_amount}")
    print(f"URL: {item_url}")

    # Get browser manager (will initialize on first call)
    print("\n--- Initializing browser manager ---")
    init_start = time.time()
    browser_manager = await get_browser_manager()
    init_time = time.time() - init_start
    print(f"Browser initialization took: {init_time:.2f}s")

    # First bid (includes context creation)
    print("\n--- First bid (includes context creation) ---")
    start = time.time()
    success, message = await browser_manager.place_bid_fast(
        user_id=1,  # Test with user_id 1
        session_data=session_data,
        item_url=item_url,
        bid_amount=bid_amount
    )
    first_bid_time = time.time() - start
    print(f"Result: success={success}, message={message}")
    print(f"First bid took: {first_bid_time:.2f}s")

    # Second bid (context already exists - should be faster)
    print("\n--- Second bid (reusing context) ---")
    bid_amount2 = bid_amount + 2
    start = time.time()
    success, message = await browser_manager.place_bid_fast(
        user_id=1,
        session_data=session_data,
        item_url=item_url,
        bid_amount=bid_amount2
    )
    second_bid_time = time.time() - start
    print(f"Result: success={success}, message={message}")
    print(f"Second bid took: {second_bid_time:.2f}s")

    # Third bid
    print("\n--- Third bid (reusing context) ---")
    bid_amount3 = bid_amount2 + 2
    start = time.time()
    success, message = await browser_manager.place_bid_fast(
        user_id=1,
        session_data=session_data,
        item_url=item_url,
        bid_amount=bid_amount3
    )
    third_bid_time = time.time() - start
    print(f"Result: success={success}, message={message}")
    print(f"Third bid took: {third_bid_time:.2f}s")

    # Summary
    print("\n=== SUMMARY ===")
    print(f"Browser init: {init_time:.2f}s (one-time cost)")
    print(f"First bid: {first_bid_time:.2f}s (includes context setup)")
    print(f"Second bid: {second_bid_time:.2f}s")
    print(f"Third bid: {third_bid_time:.2f}s")
    avg = (first_bid_time + second_bid_time + third_bid_time) / 3
    print(f"Average per bid: {avg:.2f}s")

    # Cleanup
    print("\n--- Cleaning up ---")
    await browser_manager.shutdown()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_fast_bid())
