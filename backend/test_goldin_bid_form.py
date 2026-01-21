"""
Test what happens when clicking 'Place Bid' on Goldin
"""
import asyncio
from playwright.async_api import async_playwright

async def test_bid_form():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()

        # Go directly to an active item
        url = "https://goldin.co/item/1997-98-upper-deck-sp-authentic-signs-of-the-times-stars-rookies-mj-mivb79z"
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # Accept cookies
        accept_btn = await page.query_selector('button:has-text("Accept")')
        if accept_btn:
            await accept_btn.click()
            await asyncio.sleep(1)

        await page.screenshot(path="goldin_before_placebid.png")
        print("Screenshot: goldin_before_placebid.png")

        # Click "Place Bid" button
        place_bid_btn = await page.query_selector('button:has-text("Place Bid")')
        if place_bid_btn:
            print("Clicking 'Place Bid' button...")
            await place_bid_btn.click()
            await asyncio.sleep(3)

            await page.screenshot(path="goldin_after_placebid.png")
            print("Screenshot: goldin_after_placebid.png")
            print(f"Current URL: {page.url}")

            # Look for modal/dialog
            print("\n=== LOOKING FOR MODAL/DIALOG ===")
            dialogs = await page.query_selector_all('[role="dialog"], [role="modal"], .modal, [class*="modal"], [class*="Modal"]')
            print(f"Found {len(dialogs)} modal-like elements")

            # Look for ALL inputs now
            print("\n=== ALL INPUTS AFTER CLICKING ===")
            inputs = await page.query_selector_all('input')
            for inp in inputs:
                html = await inp.evaluate('el => el.outerHTML')
                print(f"  {html[:400]}")

            # Look for ALL buttons now
            print("\n=== ALL BUTTONS AFTER CLICKING ===")
            buttons = await page.query_selector_all('button')
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                if text and len(text) < 80:
                    is_visible = await btn.is_visible()
                    print(f"  '{text}' (visible: {is_visible})")

            # Check for login prompt
            print("\n=== LOOKING FOR LOGIN PROMPT ===")
            login_text = await page.query_selector('text=Sign In, text=Login, text=Log In')
            if login_text:
                print("Login prompt detected!")

            # Look for any currency/bid input patterns
            print("\n=== LOOKING FOR CURRENCY INPUTS ===")
            currency_elements = await page.query_selector_all('[class*="currency"], [class*="bid"], [class*="amount"], [inputmode="numeric"]')
            for el in currency_elements:
                html = await el.evaluate('el => el.outerHTML')
                print(f"  {html[:300]}")

        else:
            print("Could not find 'Place Bid' button!")

        await browser.close()

asyncio.run(test_bid_form())
