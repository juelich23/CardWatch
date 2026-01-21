"""
Intercept ALL network requests during bid flow
"""
import asyncio
import sys
import json
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from playwright.async_api import async_playwright

# Get session
import sqlite3
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

from app.services.encryption import get_encryption_service
encryption = get_encryption_service()
session_json = encryption.decrypt(row[0], row[1])
session_data = json.loads(session_json)

async def intercept_all():
    # Get a cheap item
    conn = sqlite3.connect('auction_data.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_url, title, current_bid, external_id FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid > 0
        ORDER BY current_bid ASC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    item_url, title, current_bid, external_id = row
    bid_amount = int(current_bid) + 10  # Bid higher

    print(f"Item: {title[:50]}...")
    print(f"External ID: {external_id}")
    print(f"Current bid: ${current_bid}")
    print(f"Our bid: ${bid_amount}")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport={'width': 1920, 'height': 1080},
    )

    # Restore session
    if session_data.get("cookies"):
        await context.add_cookies(session_data["cookies"])

    page = await context.new_page()

    # Restore localStorage
    if session_data.get("localStorage"):
        await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=30000)
        for key, value in session_data["localStorage"].items():
            await page.evaluate("(args) => localStorage.setItem(args.key, args.value)", {"key": key, "value": value})

    # Set up request interception for ALL POST requests
    all_posts = []
    all_websockets = []

    async def handle_request(request):
        if request.method == 'POST':
            all_posts.append({
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data
            })
            # Print immediately for POST requests
            if 'cloudfront' in request.url or 'goldin' in request.url:
                print(f"\n>>> POST: {request.url}")
                if request.post_data:
                    print(f"    Data: {request.post_data[:200]}")

    async def handle_response(response):
        if response.request.method == 'POST':
            for call in all_posts:
                if call['url'] == response.url and 'response_status' not in call:
                    call['response_status'] = response.status
                    try:
                        body = await response.text()
                        call['response_body'] = body[:500] if len(body) > 500 else body
                        if 'cloudfront' in response.url or 'goldin' in response.url:
                            print(f"    Status: {response.status}, Response: {body[:200]}")
                    except:
                        pass
                    break

    page.on('request', handle_request)
    page.on('response', handle_response)

    # Also monitor WebSockets
    def handle_websocket(ws):
        print(f"\n>>> WEBSOCKET: {ws.url}")
        all_websockets.append({'url': ws.url, 'messages': []})

        def on_message(payload):
            print(f"    WS Message: {str(payload)[:200]}")
            all_websockets[-1]['messages'].append(str(payload))

        ws.on('framereceived', lambda payload: on_message(payload))
        ws.on('framesent', lambda payload: on_message(payload))

    page.on('websocket', handle_websocket)

    try:
        print("\n=== Starting bid flow ===")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
        except:
            pass

        print("\n--- Clicking Place Bid ---")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        print("\n--- Entering bid amount ---")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        print("\n--- Clicking submit (Place Bid button) ---")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and text == "Place Bid":
                await btn.click()
                break
        await asyncio.sleep(2)

        print("\n--- Clicking Confirm Your Bid ---")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and "Confirm Your Bid" in text:
                await btn.click()
                break

        # Wait for bid to process
        print("\n--- Waiting for bid response ---")
        await asyncio.sleep(5)

        # Summary
        print(f"\n\n=== SUMMARY ===")
        print(f"Total POST requests: {len(all_posts)}")
        print(f"Total WebSockets: {len(all_websockets)}")

        # Look for bid-related calls
        print("\n=== BID-RELATED POSTS ===")
        for call in all_posts:
            url_lower = call['url'].lower()
            post_data = (call.get('post_data') or '').lower()
            if 'bid' in url_lower or 'bid' in post_data or 'place' in url_lower:
                print(f"\nURL: {call['url']}")
                print(f"Data: {call.get('post_data')}")
                print(f"Status: {call.get('response_status')}")
                print(f"Response: {call.get('response_body', '')[:300]}")

        if all_websockets:
            print("\n=== WEBSOCKET MESSAGES ===")
            for ws in all_websockets:
                print(f"\nWS URL: {ws['url']}")
                for msg in ws['messages'][:10]:
                    print(f"  {msg[:200]}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(intercept_all())
