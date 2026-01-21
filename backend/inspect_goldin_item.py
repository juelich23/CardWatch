"""
Inspect Goldin item page to find bid form elements
"""
import asyncio
from playwright.async_api import async_playwright

async def inspect_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")  # Non-headless to see
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()

        # Navigate to an item page
        url = "https://goldin.co/item/2024-25-upper-deck-clear-cut-autographs-cc-pb-peter-bondra-signed-card-psa-mint-9-uxadrq"
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(5)

        # Take screenshot
        await page.screenshot(path="goldin_item_page.png", full_page=True)
        print("Screenshot saved to goldin_item_page.png")

        # Find all input elements
        print("\n=== INPUT ELEMENTS ===")
        inputs = await page.query_selector_all('input')
        for inp in inputs:
            input_type = await inp.get_attribute('type') or 'text'
            input_name = await inp.get_attribute('name') or ''
            input_placeholder = await inp.get_attribute('placeholder') or ''
            input_class = await inp.get_attribute('class') or ''
            input_id = await inp.get_attribute('id') or ''
            print(f"  type={input_type}, name={input_name}, placeholder={input_placeholder}, id={input_id}")
            print(f"    class: {input_class[:100]}...")

        # Find all buttons
        print("\n=== BUTTON ELEMENTS ===")
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            btn_text = await btn.inner_text()
            btn_class = await btn.get_attribute('class') or ''
            btn_type = await btn.get_attribute('type') or ''
            if btn_text.strip():
                print(f"  text='{btn_text.strip()[:50]}', type={btn_type}")

        # Look for bid-related elements
        print("\n=== BID-RELATED ELEMENTS ===")
        bid_elements = await page.query_selector_all('[class*="bid" i], [id*="bid" i], [data-testid*="bid" i]')
        for el in bid_elements:
            tag = await el.evaluate('el => el.tagName')
            text = await el.inner_text()
            print(f"  <{tag}>: {text[:100] if text else '(no text)'}")

        # Look for currency input patterns
        print("\n=== CURRENCY/AMOUNT INPUTS ===")
        currency_inputs = await page.query_selector_all('input[type="number"], input[inputmode="numeric"], input[pattern*="[0-9]"]')
        for inp in currency_inputs:
            html = await inp.evaluate('el => el.outerHTML')
            print(f"  {html[:200]}")

        # Dump relevant page sections
        print("\n=== PAGE TEXT (looking for bid section) ===")
        page_text = await page.inner_text('body')
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            if 'bid' in line.lower() or 'place' in line.lower() or 'current' in line.lower():
                print(f"  {line.strip()[:100]}")

        await browser.close()

asyncio.run(inspect_page())
