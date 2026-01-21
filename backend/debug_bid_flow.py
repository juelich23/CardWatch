"""
Debug the bid flow with screenshots
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

async def debug_bid():
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

    # Enable CDP for WebSocket interception
    client = await page.context.new_cdp_session(page)
    await client.send('Network.enable')

    ws_frames = []
    bid_phase = False

    def on_ws_frame_sent(params):
        payload = params.get('response', {}).get('payloadData', '')
        ws_frames.append({'direction': 'SENT', 'payload': payload, 'bid_phase': bid_phase})
        if bid_phase:
            print(f"WS SENT: {payload[:200]}")

    client.on('Network.webSocketFrameSent', on_ws_frame_sent)

    try:
        print("\n=== Navigating to item ===")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(3)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
                await asyncio.sleep(1)
        except:
            pass

        await page.screenshot(path="/tmp/bid_step1_item_page.png")
        print("Screenshot 1: Item page")

        # Step 1: Click Place Bid to open modal
        print("\n=== Step 1: Click Place Bid ===")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        await page.screenshot(path="/tmp/bid_step2_modal_open.png")
        print("Screenshot 2: Modal open")

        # List all visible buttons
        print("\nAll visible buttons:")
        buttons = await page.query_selector_all('button')
        for i, btn in enumerate(buttons):
            try:
                if await btn.is_visible():
                    text = (await btn.inner_text()).strip()
                    if text:
                        print(f"  {i}: '{text}'")
            except:
                pass

        # Step 2: Enter bid amount
        print("\n=== Step 2: Enter bid amount ===")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        if not bid_input:
            bid_input = await page.query_selector('input[type="number"]')
        if bid_input:
            await bid_input.fill(str(bid_amount))
            await asyncio.sleep(1)
            print(f"Entered bid: ${bid_amount}")
        else:
            print("Could not find bid input!")

        await page.screenshot(path="/tmp/bid_step3_amount_entered.png")
        print("Screenshot 3: Amount entered")

        # List all visible buttons again
        print("\nButtons after entering amount:")
        buttons = await page.query_selector_all('button')
        for i, btn in enumerate(buttons):
            try:
                if await btn.is_visible():
                    text = (await btn.inner_text()).strip()
                    if text:
                        print(f"  {i}: '{text}'")
            except:
                pass

        # Step 3: Click the submit button (should show "Place Bid" text)
        print("\n=== Step 3: Click submit button ===")
        submit_clicked = False
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            try:
                text = (await btn.inner_text()).strip()
                # Look for exactly "Place Bid" text, not "Place Bid $X"
                if await btn.is_visible() and text == "Place Bid":
                    print(f"Clicking submit: '{text}'")
                    await btn.click()
                    submit_clicked = True
                    break
            except:
                pass

        if not submit_clicked:
            print("Could not find submit button!")

        await asyncio.sleep(2)
        await page.screenshot(path="/tmp/bid_step4_after_submit.png")
        print("Screenshot 4: After submit")

        # List all buttons
        print("\nButtons after submit:")
        buttons = await page.query_selector_all('button')
        for i, btn in enumerate(buttons):
            try:
                if await btn.is_visible():
                    text = (await btn.inner_text()).strip()
                    if text:
                        print(f"  {i}: '{text}'")
            except:
                pass

        # Step 4: Look for confirmation button
        print("\n=== Step 4: Looking for confirmation ===")
        bid_phase = True

        # Try several selectors for confirm button
        confirm_clicked = False

        # Try text-based
        confirm_btn = await page.query_selector('button:has-text("Confirm")')
        if confirm_btn and await confirm_btn.is_visible():
            text = await confirm_btn.inner_text()
            print(f"Found confirm button: '{text}'")
            await confirm_btn.click()
            confirm_clicked = True
        else:
            # Try data-testid or other attributes
            confirm_btn = await page.query_selector('[data-testid*="confirm"]')
            if confirm_btn:
                await confirm_btn.click()
                confirm_clicked = True
                print("Clicked via data-testid")
            else:
                # Look for any button with Confirm in the text
                buttons = await page.query_selector_all('button')
                for btn in buttons:
                    try:
                        text = (await btn.inner_text()).strip()
                        if await btn.is_visible() and 'confirm' in text.lower():
                            print(f"Clicking confirm: '{text}'")
                            await btn.click()
                            confirm_clicked = True
                            break
                    except:
                        pass

        if not confirm_clicked:
            print("Could not find confirm button!")

        await asyncio.sleep(3)
        await page.screenshot(path="/tmp/bid_step5_after_confirm.png")
        print("Screenshot 5: After confirm")

        bid_phase = False

        # Check result
        print("\n=== Checking result ===")
        page_text = await page.inner_text('body')

        # Look for success/error messages
        if 'highest bidder' in page_text.lower():
            print("SUCCESS: You are the highest bidder!")
        elif 'bid placed' in page_text.lower():
            print("SUCCESS: Bid placed!")
        elif 'error' in page_text.lower():
            print("ERROR detected in page")
        elif 'outbid' in page_text.lower():
            print("You were outbid")

        # Show WS frames during bid
        print(f"\n=== WS frames during bid: {len([f for f in ws_frames if f['bid_phase']])} ===")
        for frame in ws_frames:
            if frame['bid_phase']:
                print(f"  {frame['direction']}: {frame['payload'][:200]}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        await page.screenshot(path="/tmp/bid_error.png")
    finally:
        await browser.close()
        await p.stop()

    print("\nScreenshots saved to /tmp/bid_step*.png")

asyncio.run(debug_bid())
