"""
Use Playwright route interception to capture the exact bid request
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

async def intercept_route():
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
    bid_amount = int(current_bid) + 2

    print(f"Item: {title[:50]}...")
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

    # Set up route interception for ALL requests
    captured_requests = []

    async def handle_route(route):
        request = route.request
        captured_requests.append({
            'url': request.url,
            'method': request.method,
            'post_data': request.post_data,
            'headers': dict(request.headers)
        })

        # Print bid-related requests immediately
        if 'bid' in request.url.lower() or 'place' in request.url.lower():
            print(f"\n>>> CAPTURED: {request.method} {request.url}")
            if request.post_data:
                print(f"    Data: {request.post_data}")
            print(f"    Headers: {dict(request.headers)}")

        # Continue the request
        await route.continue_()

    # Intercept all cloudfront and goldin requests
    await page.route("**/*", handle_route)

    try:
        print("\n=== Navigating to item ===")
        await page.goto(item_url, wait_until="networkidle", timeout=60000)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
                await asyncio.sleep(1)
        except:
            pass

        print("\n=== Clicking Place Bid to open modal ===")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        print("\n=== Entering bid amount ===")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        if not bid_input:
            bid_input = await page.query_selector('input[type="number"]')
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        print("\n=== Clicking submit button ===")
        # Get all buttons
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            try:
                text = (await btn.inner_text()).strip()
                if await btn.is_visible() and text == "Place Bid":
                    await btn.click()
                    break
            except:
                pass
        await asyncio.sleep(2)

        print("\n=== Looking for and clicking confirm ===")

        # List visible buttons
        buttons = await page.query_selector_all('button')
        print("Visible buttons:")
        for btn in buttons:
            try:
                if await btn.is_visible():
                    text = (await btn.inner_text()).strip()
                    print(f"  - '{text}'")
            except:
                pass

        # Try to find confirm button
        confirm_btn = None
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            try:
                if await btn.is_visible():
                    text = (await btn.inner_text()).strip()
                    if 'confirm' in text.lower():
                        confirm_btn = btn
                        print(f"\nFound confirm button: '{text}'")
                        break
            except:
                pass

        if confirm_btn:
            print("\n=== CLICKING CONFIRM - WATCH FOR BID REQUEST ===")
            await confirm_btn.click()
            await asyncio.sleep(5)

        print(f"\n\n=== CAPTURED {len(captured_requests)} REQUESTS ===")

        # Filter for bid-related
        print("\n=== BID-RELATED REQUESTS ===")
        for req in captured_requests:
            url = req['url'].lower()
            post_data = (req.get('post_data') or '').lower()
            if 'bid' in url or 'bid' in post_data or 'place' in url:
                print(f"\n{req['method']} {req['url']}")
                if req.get('post_data'):
                    print(f"  Data: {req['post_data'][:500]}")

        # Look for POST requests to cloudfront
        print("\n=== ALL CLOUDFRONT POST REQUESTS ===")
        for req in captured_requests:
            if 'cloudfront' in req['url'] and req['method'] == 'POST':
                print(f"\nPOST {req['url']}")
                if req.get('post_data'):
                    print(f"  Data: {req['post_data'][:500]}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(intercept_route())
