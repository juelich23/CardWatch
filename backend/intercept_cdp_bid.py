"""
Use Chrome DevTools Protocol to intercept ALL network traffic during bid
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

async def intercept_cdp():
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

    # Use CDP to intercept network
    client = await page.context.new_cdp_session(page)
    await client.send('Network.enable')

    all_requests = []
    bid_phase = False

    def on_request(params):
        url = params.get('request', {}).get('url', '')
        method = params.get('request', {}).get('method', '')
        post_data = params.get('request', {}).get('postData', '')
        headers = params.get('request', {}).get('headers', {})

        req_info = {
            'url': url,
            'method': method,
            'post_data': post_data,
            'headers': headers,
            'bid_phase': bid_phase,
            'request_id': params.get('requestId')
        }
        all_requests.append(req_info)

        # Print immediately if it looks like a bid-related POST
        if method == 'POST' and bid_phase:
            print(f"\n>>> CDP POST during bid: {url[:100]}")
            if post_data:
                print(f"    Data: {post_data[:300]}")

    def on_response(params):
        request_id = params.get('requestId')
        for req in all_requests:
            if req.get('request_id') == request_id:
                req['status'] = params.get('response', {}).get('status')
                break

    client.on('Network.requestWillBeSent', on_request)
    client.on('Network.responseReceived', on_response)

    # Also listen for WebSocket frames
    await client.send('Network.enable')

    ws_frames = []

    def on_ws_created(params):
        print(f"\n>>> CDP WebSocket created: {params.get('url', '')[:100]}")

    def on_ws_frame_sent(params):
        payload = params.get('response', {}).get('payloadData', '')
        ws_frames.append({'direction': 'SENT', 'payload': payload, 'bid_phase': bid_phase})
        if bid_phase:
            print(f"\n>>> CDP WS SENT: {payload[:200]}")

    def on_ws_frame_received(params):
        payload = params.get('response', {}).get('payloadData', '')
        ws_frames.append({'direction': 'RECV', 'payload': payload, 'bid_phase': bid_phase})
        # Only print bid-related WS frames
        if bid_phase and ('bid' in payload.lower() or 'current' in payload.lower()):
            print(f"\n>>> CDP WS RECV: {payload[:200]}")

    client.on('Network.webSocketCreated', on_ws_created)
    client.on('Network.webSocketFrameSent', on_ws_frame_sent)
    client.on('Network.webSocketFrameReceived', on_ws_frame_received)

    try:
        print("\n=== Navigating to item ===")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
        except:
            pass

        print("\n=== Clicking Place Bid (opening modal) ===")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        print("\n=== Entering bid amount ===")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        if not bid_input:
            bid_input = await page.query_selector('input[type="number"]')
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        print("\n=== Clicking Place Bid (submit) ===")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and text == "Place Bid":
                await btn.click()
                break
        await asyncio.sleep(2)

        print("\n\n=== NOW CONFIRMING BID - WATCHING NETWORK ===")
        bid_phase = True

        # Click confirm button
        confirm_clicked = False
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            try:
                text = (await btn.inner_text()).strip()
                if await btn.is_visible() and "Confirm Your Bid" in text:
                    print(f"Clicking confirm button: {text}")
                    await btn.click()
                    confirm_clicked = True
                    break
            except:
                pass

        if not confirm_clicked:
            print("WARNING: Could not find confirm button!")
            # Try to find any button with confirm text
            confirm_btn = await page.query_selector('button:has-text("Confirm")')
            if confirm_btn:
                await confirm_btn.click()
                confirm_clicked = True
                print("Clicked generic Confirm button")

        # Wait for network activity
        await asyncio.sleep(5)
        bid_phase = False

        # Summary
        print(f"\n\n=== SUMMARY ===")
        print(f"Total requests: {len(all_requests)}")
        print(f"Total WS frames: {len(ws_frames)}")

        # Show all requests during bid phase
        print("\n=== REQUESTS DURING BID PHASE ===")
        for req in all_requests:
            if req['bid_phase']:
                print(f"\n{req['method']} {req['url'][:100]}")
                if req.get('post_data'):
                    print(f"  Data: {req['post_data'][:500]}")
                if req.get('status'):
                    print(f"  Status: {req['status']}")

        # Show WS frames during bid phase
        print("\n=== WS FRAMES DURING BID PHASE ===")
        for frame in ws_frames:
            if frame['bid_phase']:
                print(f"\n{frame['direction']}: {frame['payload'][:300]}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(intercept_cdp())
