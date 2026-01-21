"""
Test the exact bid flow to diagnose timeouts
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

async def test_bid_flow():
    item_url = "https://goldin.co/item/2024-25-upper-deck-clear-cut-cc-pb-peter-bondra-signed-card-upper-deckxpjq7"

    print(f"\n=== Starting bid flow test ===")
    print(f"Item URL: {item_url}")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport={'width': 1920, 'height': 1080},
    )

    # Restore cookies
    if session_data.get("cookies"):
        print(f"Restoring {len(session_data['cookies'])} cookies...")
        await context.add_cookies(session_data["cookies"])

    page = await context.new_page()

    try:
        # Step 1: Navigate to page
        print(f"\n[1] Navigating to item page...")
        import time
        start = time.time()
        await page.goto(item_url, wait_until="load", timeout=30000)
        print(f"    Page loaded in {time.time() - start:.2f}s")

        # Step 2: Accept cookies (with short timeout, skip if fails)
        print(f"\n[2] Checking for cookie banner...")
        try:
            accept_btn = await page.query_selector('button:has-text("Accept")')
            if accept_btn and await accept_btn.is_visible():
                print("    Clicking Accept...")
                await accept_btn.click(timeout=5000)
                await asyncio.sleep(1)
            else:
                print("    No visible cookie banner")
        except Exception as e:
            print(f"    Cookie banner skipped: {e}")

        # Step 3: Wait for Place Bid button
        print(f"\n[3] Waiting for Place Bid button...")
        start = time.time()
        try:
            place_bid_button = await page.wait_for_selector(
                'button:has-text("Place Bid")',
                timeout=30000
            )
            print(f"    Button found in {time.time() - start:.2f}s")
        except Exception as e:
            print(f"    ERROR: {e}")
            await page.screenshot(path="/tmp/bid_flow_error.png")
            print("    Screenshot saved to /tmp/bid_flow_error.png")

            # Check page content
            body = await page.inner_text('body')
            if 'Lot Not Found' in body:
                print("    Page shows: Lot Not Found")
            elif 'Must be signed in' in body:
                print("    Page shows: Must be signed in (session invalid)")
            else:
                print(f"    Page text sample: {body[:200]}")
            return

        # Step 4: Click Place Bid
        print(f"\n[4] Clicking Place Bid button...")
        await place_bid_button.click()
        await asyncio.sleep(2)

        # Step 5: Check what appeared
        print(f"\n[5] Checking for bid modal...")

        # Check for login modal (session expired)
        login_text = await page.query_selector('text=Must be signed in')
        if login_text:
            print("    LOGIN MODAL: Session expired!")
            await page.screenshot(path="/tmp/bid_flow_login.png")
            return

        # Look for bid input
        inputs = await page.query_selector_all('input')
        print(f"    Found {len(inputs)} input elements")
        for inp in inputs:
            try:
                inp_type = await inp.get_attribute('type')
                placeholder = await inp.get_attribute('placeholder')
                is_visible = await inp.is_visible()
                print(f"      - type={inp_type}, placeholder={placeholder}, visible={is_visible}")
            except:
                pass

        await page.screenshot(path="/tmp/bid_flow_modal.png")
        print("    Screenshot saved to /tmp/bid_flow_modal.png")

        print(f"\n=== Test complete ===")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

asyncio.run(test_bid_flow())
