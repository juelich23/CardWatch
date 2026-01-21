"""
Find and inspect an active Goldin auction item to see bid form structure
"""
import asyncio
from playwright.async_api import async_playwright

async def inspect_active_auction():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()

        # Go to Goldin homepage
        print("Navigating to Goldin homepage...")
        await page.goto("https://goldin.co/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # Wait for JS to render

        # Accept cookies
        accept_btn = await page.query_selector('button:has-text("Accept")')
        if accept_btn:
            await accept_btn.click()
            await asyncio.sleep(1)

        await page.screenshot(path="goldin_home.png")
        print("Homepage screenshot saved")

        # Try clicking "Bid Now" button
        bid_now_btn = await page.query_selector('button:has-text("Bid Now"), a:has-text("Bid Now")')
        if bid_now_btn:
            print("Found 'Bid Now' button, clicking...")
            await bid_now_btn.click()
            await asyncio.sleep(5)
            await page.screenshot(path="goldin_after_bidnow.png")
            print(f"After Bid Now URL: {page.url}")

        # Look for item links
        item_links = await page.query_selector_all('a[href*="/item/"]')
        print(f"Found {len(item_links)} item links")

        if not item_links:
            # Try scrolling down to load more
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            item_links = await page.query_selector_all('a[href*="/item/"]')
            print(f"After scroll: Found {len(item_links)} item links")

        if item_links:
            # Get first item href and navigate directly
            first_href = await item_links[0].get_attribute('href')
            print(f"First item: {first_href}")

            # Navigate directly to avoid stale element
            if first_href.startswith('/'):
                first_href = f"https://goldin.co{first_href}"
            await page.goto(first_href, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)

            await page.screenshot(path="goldin_item_active.png", full_page=True)
            print(f"Item page: {page.url}")

            # Inspect ALL elements
            print("\n=== ALL INPUT ELEMENTS ===")
            inputs = await page.query_selector_all('input')
            for inp in inputs:
                html = await inp.evaluate('el => el.outerHTML')
                print(f"  {html[:300]}")

            print("\n=== ALL BUTTONS WITH TEXT ===")
            buttons = await page.query_selector_all('button')
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                if text and len(text) < 60:
                    print(f"  Button: '{text}'")

            print("\n=== TEXT WITH 'BID' ===")
            body_text = await page.inner_text('body')
            for line in body_text.split('\n'):
                line = line.strip()
                if 'bid' in line.lower() and len(line) < 100:
                    print(f"  {line}")

            print("\n=== TEXT WITH '$' ===")
            for line in body_text.split('\n'):
                line = line.strip()
                if '$' in line and len(line) < 100:
                    print(f"  {line}")

        await browser.close()

asyncio.run(inspect_active_auction())
