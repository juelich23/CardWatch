"""
Intercept Goldin's bid API calls to find the endpoint
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

# Get auth tokens from localStorage
local_storage = session_data.get('localStorage', {})
print("=== AUTH TOKENS IN LOCALSTORAGE ===")
for key, value in local_storage.items():
    if 'token' in key.lower() or 'cognito' in key.lower():
        # Truncate long values
        val_display = value[:100] + "..." if len(value) > 100 else value
        print(f"{key}: {val_display}")

async def intercept_bid_api():
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

    print(f"\n=== INTERCEPTING BID API ===")
    print(f"Item: {title[:50]}...")
    print(f"External ID: {external_id}")
    print(f"Bidding: ${bid_amount}")

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

    # Set up request interception
    api_calls = []

    async def handle_request(request):
        url = request.url
        # Look for API calls
        if 'api' in url.lower() or 'graphql' in url.lower() or 'bid' in url.lower():
            api_calls.append({
                'url': url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data
            })

    async def handle_response(response):
        url = response.url
        if 'api' in url.lower() or 'graphql' in url.lower() or 'bid' in url.lower():
            try:
                body = await response.text()
                for call in api_calls:
                    if call['url'] == url:
                        call['response_status'] = response.status
                        call['response_body'] = body[:2000] if len(body) > 2000 else body
            except:
                pass

    page.on('request', handle_request)
    page.on('response', handle_response)

    try:
        print("\nNavigating to item...")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
        except:
            pass

        print("Clicking Place Bid...")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        print("Entering bid amount...")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        print("Clicking submit...")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and text == "Place Bid":
                await btn.click()
                break
        await asyncio.sleep(2)

        print("Clicking Confirm Your Bid...")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and "Confirm Your Bid" in text:
                await btn.click()
                break
        await asyncio.sleep(3)

        print(f"\n=== CAPTURED {len(api_calls)} API CALLS ===")
        for i, call in enumerate(api_calls):
            print(f"\n--- Call {i+1} ---")
            print(f"URL: {call['url']}")
            print(f"Method: {call['method']}")
            if call.get('post_data'):
                print(f"Post Data: {call['post_data'][:500]}")
            if call.get('response_status'):
                print(f"Status: {call['response_status']}")
            if call.get('response_body'):
                print(f"Response: {call['response_body'][:500]}")

            # Look for auth headers
            auth_headers = {k: v for k, v in call['headers'].items()
                          if 'auth' in k.lower() or 'token' in k.lower() or 'bearer' in k.lower()}
            if auth_headers:
                print(f"Auth Headers: {auth_headers}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(intercept_bid_api())
