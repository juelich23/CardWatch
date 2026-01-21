"""
Inspect Goldin's bid modal structure to understand the button selectors
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

from app.services.encryption import get_encryption_service
encryption = get_encryption_service()
session_json = encryption.decrypt(encrypted_state, iv)
session_data = json.loads(session_json)

async def inspect_modal():
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

    if not row:
        print("No cheap Goldin items found!")
        return

    item_url, title, current_bid = row
    print(f"Item: {title[:60]}...")
    print(f"URL: {item_url}")
    print(f"Current bid: ${current_bid}")

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
        print(f"\nNavigating to item...")
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

        # Wait for Place Bid button
        print("Waiting for Place Bid button...")
        try:
            place_bid_btn = await page.wait_for_selector('button:has-text("Place Bid")', timeout=15000)
        except:
            print("Could not find Place Bid button!")
            body = await page.inner_text('body')
            if 'Must be signed in' in body:
                print("SESSION EXPIRED!")
            return

        print("Clicking Place Bid button...")
        await place_bid_btn.click()
        await asyncio.sleep(2)

        # Save screenshot of modal
        try:
            await page.screenshot(path="/tmp/goldin_modal.png", timeout=10000)
            print("Screenshot saved to /tmp/goldin_modal.png")
        except Exception as e:
            print(f"Screenshot failed: {e}")

        # Check for login modal
        login_text = await page.query_selector('text=Must be signed in')
        if login_text:
            print("\n*** SESSION EXPIRED - Need to re-login! ***")
            return

        # Inspect the modal structure
        print("\n=== MODAL STRUCTURE ===")

        # Find all dialogs/modals
        modals = await page.query_selector_all('[role="dialog"], [role="modal"], .modal, [class*="modal" i], [class*="Modal"]')
        print(f"Found {len(modals)} modal-like elements")

        # Find all inputs in the modal area
        print("\n=== INPUTS ===")
        inputs = await page.query_selector_all('input')
        for inp in inputs:
            try:
                visible = await inp.is_visible()
                if visible:
                    attrs = await inp.evaluate('''el => ({
                        type: el.type,
                        placeholder: el.placeholder,
                        name: el.name,
                        id: el.id,
                        class: el.className
                    })''')
                    print(f"  VISIBLE: {attrs}")
            except:
                pass

        # Find all buttons
        print("\n=== BUTTONS ===")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            try:
                visible = await btn.is_visible()
                text = (await btn.inner_text()).strip()
                if visible and text:
                    # Get parent element to understand context
                    in_modal = await btn.evaluate('''el => {
                        let parent = el.parentElement;
                        while (parent) {
                            if (parent.getAttribute('role') === 'dialog' ||
                                parent.className.toLowerCase().includes('modal')) {
                                return true;
                            }
                            parent = parent.parentElement;
                        }
                        return false;
                    }''')
                    print(f"  '{text[:40]}' - visible={visible}, in_modal={in_modal}")
            except:
                pass

        # Look for specific modal container
        print("\n=== LOOKING FOR CONFIRM IN DIALOG ===")
        dialog_buttons = await page.query_selector_all('[role="dialog"] button')
        print(f"Found {len(dialog_buttons)} buttons inside [role='dialog']")
        for btn in dialog_buttons:
            try:
                text = (await btn.inner_text()).strip()
                visible = await btn.is_visible()
                print(f"  Dialog button: '{text}' (visible={visible})")
            except:
                pass

        # Check for any overlay/backdrop
        print("\n=== OVERLAY CHECK ===")
        overlays = await page.query_selector_all('[class*="overlay" i], [class*="backdrop" i]')
        print(f"Found {len(overlays)} overlay elements")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(inspect_modal())
