"""
Debug what happens after clicking submit
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
    conn = sqlite3.connect('auction_data.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT item_url, title, current_bid FROM auction_items
        WHERE auction_house = 'goldin' AND status = 'Live' AND current_bid = 10
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    item_url, title, current_bid = row
    bid_amount = 14  # Slightly higher

    print(f"Item: {title[:50]}...")
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
    if session_data.get("localStorage"):
        page = await context.new_page()
        await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=30000)
        for key, value in session_data["localStorage"].items():
            await page.evaluate("(args) => localStorage.setItem(args.key, args.value)", {"key": key, "value": value})
        await page.close()

    page = await context.new_page()

    try:
        print("\n[1] Navigating...")
        await page.goto(item_url, wait_until="load", timeout=30000)
        await asyncio.sleep(2)

        # Accept cookies
        try:
            btn = await page.query_selector('button:has-text("Accept")')
            if btn and await btn.is_visible():
                await btn.click(timeout=5000)
        except:
            pass

        print("[2] Clicking Place Bid...")
        place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        await place_bid_btn.click()
        await asyncio.sleep(2)

        # Check for login
        login_text = await page.query_selector('text=Must be signed in')
        if login_text:
            print("SESSION EXPIRED!")
            return

        print("[3] Entering bid...")
        bid_input = await page.query_selector('input[placeholder*="Amount" i]')
        await bid_input.fill(str(bid_amount))
        await asyncio.sleep(1)

        print("[4] Clicking submit...")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if await btn.is_visible() and text == "Place Bid":
                await btn.click()
                break

        print("[5] Waiting 5 seconds...")
        await asyncio.sleep(5)

        # Check current URL
        print(f"Current URL: {page.url}")

        # Get page text
        page_text = await page.inner_text('body')

        print("\n=== PAGE TEXT (looking for bid-related content) ===")
        for line in page_text.split('\n'):
            line = line.strip()
            lower = line.lower()
            if any(kw in lower for kw in ['bid', 'confirm', 'success', 'error', 'fail', 'place', 'high', 'amount']):
                if len(line) < 150:
                    print(f"  {line}")

        # Check for dialogs/modals
        print("\n=== DIALOGS ===")
        dialogs = await page.query_selector_all('[role="dialog"]')
        print(f"Found {len(dialogs)} dialogs")
        for d in dialogs:
            try:
                text = await d.inner_text()
                visible = await d.is_visible()
                print(f"  visible={visible}, text={text[:200]}...")
            except:
                pass

        # Check for any alert/error
        print("\n=== ALERTS ===")
        alerts = await page.query_selector_all('[role="alert"]')
        print(f"Found {len(alerts)} alerts")
        for a in alerts:
            try:
                text = await a.inner_text()
                print(f"  {text}")
            except:
                pass

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(debug_bid())
