"""
Visual test of bid flow - headless=False to see what's happening
"""
import asyncio
import sys
import json
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from playwright.async_api import async_playwright

# Get session data from database
import sqlite3
conn = sqlite3.connect('auction_data.db')
cursor = conn.cursor()

# Get the active session
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

encrypted_state, iv = row
print(f"Found session with IV: {iv[:20]}...")

# Decrypt the session
from app.services.encryption import get_encryption_service
encryption = get_encryption_service()
session_json = encryption.decrypt(encrypted_state, iv)
session_data = json.loads(session_json)
print(f"Session has {len(session_data.get('cookies', []))} cookies")
print(f"Session has {len(session_data.get('localStorage', {}))} localStorage items")

# Show localStorage keys
if session_data.get('localStorage'):
    print("localStorage keys:", list(session_data['localStorage'].keys()))

async def test_bid_visual():
    # Pick an active Goldin item
    conn = sqlite3.connect('auction_data.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_url, title, current_bid FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'active'
        ORDER BY end_time ASC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if not row:
        print("No active Goldin items found!")
        return

    item_url, title, current_bid = row
    bid_amount = max(1, (current_bid or 0) + 1)  # Minimum bid

    print(f"\n=== Visual Bid Test ===")
    print(f"Item: {title[:60]}...")
    print(f"URL: {item_url}")
    print(f"Current bid: ${current_bid}")
    print(f"Our bid: ${bid_amount}")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=False, channel="chrome")  # VISIBLE
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport={'width': 1920, 'height': 1080},
    )

    # Restore cookies
    if session_data.get("cookies"):
        print(f"\nRestoring {len(session_data['cookies'])} cookies...")
        await context.add_cookies(session_data["cookies"])

    # Restore localStorage
    if session_data.get("localStorage"):
        print(f"Restoring {len(session_data['localStorage'])} localStorage items...")
        page = await context.new_page()
        await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=30000)
        for key, value in session_data["localStorage"].items():
            await page.evaluate(
                "(args) => localStorage.setItem(args.key, args.value)",
                {"key": key, "value": value}
            )
        await page.close()
        print("localStorage restored!")

    page = await context.new_page()

    try:
        # Step 1: Navigate to page
        print(f"\n[1] Navigating to item page...")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Step 2: Accept cookies if present
        print(f"[2] Checking for cookie banner...")
        try:
            accept_btn = await page.query_selector('button:has-text("Accept")')
            if accept_btn and await accept_btn.is_visible():
                await accept_btn.click(timeout=5000)
                await asyncio.sleep(1)
        except Exception:
            pass

        # Step 3: Wait for Place Bid button
        print(f"[3] Waiting for Place Bid button...")
        try:
            place_bid_button = await page.wait_for_selector(
                'button:has-text("Place Bid")',
                timeout=15000
            )
            print("    Found Place Bid button!")
        except Exception as e:
            print(f"    ERROR: {e}")
            body = await page.inner_text('body')
            if 'Lot Not Found' in body:
                print("    Page shows: Lot Not Found")
            elif 'Must be signed in' in body:
                print("    Page shows: Must be signed in")
            input("Press Enter to close browser...")
            return

        # Step 4: Click Place Bid
        print(f"[4] Clicking Place Bid button...")
        await place_bid_button.click()
        await asyncio.sleep(2)

        # Step 5: Check for login modal
        print(f"[5] Checking for login modal...")
        login_text = await page.query_selector('text=Must be signed in')
        if login_text:
            print("    SESSION EXPIRED - Login required!")
            input("Press Enter to close browser...")
            return

        # Step 6: Find bid input
        print(f"[6] Looking for bid input...")
        bid_input = None
        selectors = [
            'input[type="number"]',
            'input[inputmode="numeric"]',
            'input[inputmode="decimal"]',
            '[role="dialog"] input',
            'input[placeholder*="bid" i]',
            'input[placeholder*="amount" i]',
        ]
        for selector in selectors:
            bid_input = await page.query_selector(selector)
            if bid_input and await bid_input.is_visible():
                print(f"    Found with: {selector}")
                break
            bid_input = None

        if not bid_input:
            print("    Could not find bid input!")
            # List all inputs
            inputs = await page.query_selector_all('input')
            print(f"    Found {len(inputs)} total inputs:")
            for inp in inputs:
                attrs = await inp.evaluate('el => ({type: el.type, placeholder: el.placeholder, visible: el.offsetParent !== null})')
                print(f"      {attrs}")
            input("Press Enter to close browser...")
            return

        # Step 7: Enter bid
        print(f"[7] Entering bid amount: ${bid_amount}")
        await bid_input.click()
        await bid_input.fill("")
        await bid_input.fill(str(int(bid_amount)))
        await asyncio.sleep(1)

        # Step 8: Find confirm button
        print(f"[8] Looking for confirm button...")
        confirm_button = await page.query_selector(
            'button:has-text("Confirm"), button:has-text("Submit"), '
            'button:has-text("Place Bid"), button:has-text("Bid")'
        )
        if not confirm_button:
            print("    Could not find confirm button!")
            buttons = await page.query_selector_all('button')
            print(f"    Found {len(buttons)} buttons:")
            for btn in buttons:
                text = await btn.inner_text()
                visible = await btn.is_visible()
                if text.strip() and visible:
                    print(f"      '{text.strip()[:50]}'")
            input("Press Enter to close browser...")
            return

        print(f"[9] Clicking confirm button...")
        await confirm_button.click()
        await asyncio.sleep(3)

        # Step 10: Check result
        print(f"[10] Checking result...")
        page_text = (await page.inner_text('body')).lower()

        success_texts = ['bid placed', 'successful', 'confirmed', 'you are the high bidder', 'your bid']
        for st in success_texts:
            if st in page_text:
                print(f"    SUCCESS: Found '{st}' in page!")
                break
        else:
            # Check for error
            error_el = await page.query_selector('[role="alert"], .error, .text-red-500')
            if error_el:
                error_text = await error_el.inner_text()
                print(f"    ERROR: {error_text}")
            else:
                print("    Result unclear - check the browser window")

        print("\n=== Check browser window to verify bid ===")
        input("Press Enter to close browser...")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to close browser...")
    finally:
        await browser.close()
        await p.stop()

asyncio.run(test_bid_visual())
