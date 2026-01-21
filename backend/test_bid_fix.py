"""
Test the bid fix - verify we click the right button
"""
import asyncio
import sys
import json
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from playwright.async_api import async_playwright

# Get session data
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

if not row:
    print("No active session found!")
    sys.exit(1)

from app.services.encryption import get_encryption_service
encryption = get_encryption_service()
session_json = encryption.decrypt(row[0], row[1])
session_data = json.loads(session_json)

async def test_bid():
    # Get a cheap item
    conn = sqlite3.connect('auction_data.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_url, title, current_bid FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid > 0
        ORDER BY current_bid ASC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    item_url, title, current_bid = row
    bid_amount = int(current_bid) + 2  # Bid slightly above current

    print(f"Testing bid on: {title[:50]}...")
    print(f"Current: ${current_bid}, Bidding: ${bid_amount}")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport={'width': 1920, 'height': 1080},
    )

    # Restore cookies
    if session_data.get("cookies"):
        await context.add_cookies(session_data["cookies"])

    # Restore localStorage
    if session_data.get("localStorage"):
        page = await context.new_page()
        await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=30000)
        for key, value in session_data["localStorage"].items():
            await page.evaluate(
                "(args) => localStorage.setItem(args.key, args.value)",
                {"key": key, "value": value}
            )
        await page.close()

    page = await context.new_page()

    try:
        print("\n[1] Navigating to item...")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Accept cookies
        try:
            accept_btn = await page.query_selector('button:has-text("Accept")')
            if accept_btn and await accept_btn.is_visible():
                await accept_btn.click(timeout=5000)
                await asyncio.sleep(1)
        except:
            pass

        print("[2] Waiting for Place Bid button...")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)

        print("[3] Clicking Place Bid...")
        await place_bid_btn.click()
        await asyncio.sleep(2)

        # Check for login
        login_text = await page.query_selector('text=Must be signed in')
        if login_text:
            print("*** SESSION EXPIRED ***")
            return

        print("[4] Finding bid input...")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        if not bid_input:
            bid_input = await page.query_selector('input[type="number"]')
        if not bid_input:
            print("Could not find bid input!")
            return

        print(f"[5] Entering ${bid_amount}...")
        await bid_input.click()
        await bid_input.fill("")
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        # Find exact "Place Bid" button
        print("[6] Finding submit button (exact 'Place Bid' text)...")
        confirm_button = None
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            try:
                text = (await btn.inner_text()).strip()
                is_visible = await btn.is_visible()
                if is_visible and text == "Place Bid":
                    confirm_button = btn
                    print(f"    Found button with exact text: '{text}'")
                    break
            except:
                pass

        if not confirm_button:
            print("Could not find 'Place Bid' button!")
            # List all visible buttons
            print("Available buttons:")
            for btn in buttons:
                try:
                    text = (await btn.inner_text()).strip()
                    visible = await btn.is_visible()
                    if visible and text:
                        print(f"  - '{text}'")
                except:
                    pass
            return

        print("[7] Clicking submit button...")
        await confirm_button.click()
        await asyncio.sleep(3)

        print("[8] Checking result...")
        page_text = (await page.inner_text('body')).lower()

        # Check for success
        success_markers = ['bid placed', 'successful', 'confirmed', 'high bidder', 'your bid']
        for marker in success_markers:
            if marker in page_text:
                print(f"SUCCESS: Found '{marker}' in page!")
                return

        # Check for errors
        error_el = await page.query_selector('[role="alert"], .error, .text-red-500')
        if error_el:
            error_text = await error_el.inner_text()
            print(f"ERROR: {error_text}")
            return

        # Take screenshot
        await page.screenshot(path="/tmp/bid_result.png", timeout=5000)
        print("Result unclear - screenshot at /tmp/bid_result.png")

        # Show what's on screen
        print("\nPage contains these phrases:")
        for phrase in ['bid', 'placed', 'confirm', 'error', 'success']:
            if phrase in page_text:
                # Find the line containing this phrase
                for line in page_text.split('\n'):
                    if phrase in line and len(line) < 100:
                        print(f"  '{line.strip()}'")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(test_bid())
