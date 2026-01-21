"""
Test parallel bidding performance
"""
import asyncio
import time
import sys
import json
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

import sqlite3
from app.services.encryption import get_encryption_service
from app.services.auction_auth.browser_manager import get_browser_manager

async def test_parallel_bids():
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

    # Get multiple test items
    cursor.execute("""
        SELECT id, item_url, title, current_bid FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid > 0
        ORDER BY current_bid ASC LIMIT 3
    """)
    items = cursor.fetchall()
    conn.close()

    if not row:
        print("No active Goldin session found. Please login first.")
        return

    if len(items) < 3:
        print(f"Only found {len(items)} items. Need at least 3 for parallel test.")
        return

    encryption = get_encryption_service()
    session_json = encryption.decrypt(row[0], row[1])
    session_data = json.loads(session_json)

    print(f"=== Parallel Bidding Test ===")
    print(f"\nItems to bid on:")
    bids = []
    for item_id, item_url, title, current_bid in items:
        bid_amount = int(current_bid) + 2
        bids.append((item_url, bid_amount))
        print(f"  - {title[:50]}... (${bid_amount})")

    # Get browser manager
    print("\n--- Initializing browser manager ---")
    browser_manager = await get_browser_manager()

    # Test sequential bidding first (for comparison)
    print("\n--- Sequential bidding (3 bids) ---")
    start = time.time()
    for item_url, bid_amount in bids:
        success, message = await browser_manager.place_bid_fast(
            user_id=1,
            session_data=session_data,
            item_url=item_url,
            bid_amount=bid_amount
        )
        print(f"  Result: success={success}")
    sequential_time = time.time() - start
    print(f"Sequential time for 3 bids: {sequential_time:.2f}s")

    # Invalidate context to start fresh
    await browser_manager.invalidate_context(1)
    await asyncio.sleep(1)

    # Now test parallel bidding
    print("\n--- Parallel bidding (3 bids simultaneously) ---")

    # Need to increase bid amounts since we just bid
    parallel_bids = [(url, amount + 10) for url, amount in bids]

    start = time.time()
    results = await browser_manager.place_bids_parallel(
        user_id=1,
        session_data=session_data,
        bids=parallel_bids
    )
    parallel_time = time.time() - start

    for i, (success, message) in enumerate(results):
        print(f"  Bid {i+1}: success={success}, message={message[:50]}")

    print(f"Parallel time for 3 bids: {parallel_time:.2f}s")

    # Summary
    print("\n=== SUMMARY ===")
    print(f"Sequential (3 bids): {sequential_time:.2f}s ({sequential_time/3:.2f}s per bid)")
    print(f"Parallel (3 bids): {parallel_time:.2f}s ({parallel_time/3:.2f}s per bid effective)")
    print(f"Speedup: {sequential_time/parallel_time:.2f}x")

    # Cleanup
    await browser_manager.shutdown()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(test_parallel_bids())
