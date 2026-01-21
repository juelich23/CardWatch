"""
Test placing bid when logged into Goldin
"""
import asyncio
import sys
sys.path.insert(0, '/Users/nickjuelich/Desktop/Code/BulkBidding/backend')

from playwright.async_api import async_playwright

async def test_authenticated_bid():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()

        # First, log in
        print("Logging in to Goldin...")
        await page.goto("https://goldin.co/signIn", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Accept cookies
        accept_btn = await page.query_selector('button:has-text("Accept")')
        if accept_btn:
            await accept_btn.click()
            await asyncio.sleep(1)

        # Enter email (replace with actual test credentials or prompt)
        email_input = await page.query_selector('input[type="email"]')
        if email_input:
            # You would need real credentials here
            await email_input.fill("YOUR_EMAIL@example.com")
            await asyncio.sleep(1)

            continue_btn = await page.query_selector('button:has-text("Continue")')
            if continue_btn:
                await continue_btn.click()
                await asyncio.sleep(3)

            password_input = await page.query_selector('input[type="password"]')
            if password_input:
                await password_input.fill("YOUR_PASSWORD")
                await asyncio.sleep(1)

                submit_btn = await page.query_selector('button:has-text("Continue")')
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(5)

        print(f"After login URL: {page.url}")
        await page.screenshot(path="goldin_after_login.png")

        # Now go to an item
        item_url = "https://goldin.co/item/1997-98-upper-deck-sp-authentic-signs-of-the-times-stars-rookies-mj-mivb79z"
        print(f"Navigating to item: {item_url}")
        await page.goto(item_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        await page.screenshot(path="goldin_item_logged_in.png")

        # Click Place Bid
        place_bid_btn = await page.query_selector('button:has-text("Place Bid")')
        if place_bid_btn:
            print("Clicking Place Bid...")
            await place_bid_btn.click()
            await asyncio.sleep(3)

            await page.screenshot(path="goldin_bid_form.png")
            print("Screenshot: goldin_bid_form.png")

            # Look for inputs
            print("\n=== ALL INPUTS ===")
            inputs = await page.query_selector_all('input')
            for inp in inputs:
                html = await inp.evaluate('el => el.outerHTML')
                inp_type = await inp.get_attribute('type')
                placeholder = await inp.get_attribute('placeholder')
                print(f"  type={inp_type}, placeholder={placeholder}")
                print(f"    {html[:300]}")

            # Look for buttons
            print("\n=== ALL BUTTONS ===")
            buttons = await page.query_selector_all('button')
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                is_visible = await btn.is_visible()
                if text and is_visible:
                    print(f"  '{text}'")

        await browser.close()

# Don't actually run - this needs real credentials
print("This script needs real Goldin credentials to test.")
print("The key finding is that we need to click 'Place Bid' button first,")
print("then a modal appears where we can enter the bid amount.")
print("")
print("Update the goldin_auth.py place_bid() method to:")
print("1. Click 'Place Bid' button")
print("2. Wait for bid modal to appear")
print("3. Find bid input in modal and fill amount")
print("4. Click confirm/submit button")
