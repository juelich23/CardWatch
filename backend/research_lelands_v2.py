"""
Research Lelands - extract lot data from gallery page
"""
import asyncio
from playwright.async_api import async_playwright

async def research_lelands():
    print("Researching Lelands auction platform...")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    page = await context.new_page()

    try:
        print("\n1. Loading auction gallery...")
        await page.goto("https://auction.lelands.com/Lots/Gallery", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # Wait for JS to render

        # Get page HTML
        print("\n2. Getting page content...")
        html = await page.content()
        print(f"Page HTML length: {len(html)} chars")

        # Save HTML for analysis
        with open("/tmp/lelands_gallery.html", "w") as f:
            f.write(html)
        print("Saved HTML to /tmp/lelands_gallery.html")

        # Extract lot data using various selectors
        print("\n3. Trying to extract lot data...")

        # Look for lot containers
        lots_data = await page.evaluate("""
            () => {
                const results = {lots: [], debug: {}};

                // Try various selectors for lot containers
                const selectors = [
                    '.lot', '.lot-item', '.auction-item', '.card',
                    '[class*="lot"]', '[class*="item"]', '[data-lot]',
                    '.row .col', '.gallery-item', '.product'
                ];

                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        results.debug[sel] = els.length;
                    }
                }

                // Look for any element with lot number text
                const allText = document.body.innerText;
                const lotMatches = allText.match(/Lot #?\\d+/gi);
                if (lotMatches) {
                    results.debug['lot_numbers'] = lotMatches.slice(0, 10);
                }

                // Look for price patterns
                const priceMatches = allText.match(/\\$[\\d,]+/g);
                if (priceMatches) {
                    results.debug['prices'] = priceMatches.slice(0, 10);
                }

                // Find all links
                const links = Array.from(document.querySelectorAll('a'));
                const lotLinks = links.filter(a =>
                    a.href && (a.href.includes('/Lot/') || a.href.includes('/lot/'))
                );
                results.debug['lot_links'] = lotLinks.slice(0, 10).map(a => ({
                    href: a.href,
                    text: a.innerText.slice(0, 50)
                }));

                // Find images
                const images = Array.from(document.querySelectorAll('img'));
                const lotImages = images.filter(img =>
                    img.src && (img.src.includes('lot') || img.src.includes('Lot'))
                );
                results.debug['lot_images'] = lotImages.slice(0, 5).map(img => img.src);

                return results;
            }
        """)

        print("\nDebug info:")
        for key, value in lots_data['debug'].items():
            print(f"  {key}: {value}")

        # Check URL to see if page loaded correctly
        current_url = page.url
        print(f"\nCurrent URL: {current_url}")

        # Check for Cloudflare challenge
        has_cf = await page.evaluate("""
            () => {
                return document.body.innerText.includes('Checking your browser') ||
                       document.body.innerText.includes('challenge') ||
                       document.title.includes('Just a moment');
            }
        """)
        if has_cf:
            print("⚠️ Cloudflare challenge detected - may need different approach")
        else:
            print("✅ No Cloudflare challenge")

        # Screenshot for debugging
        await page.screenshot(path="/tmp/lelands_screenshot.png")
        print("Saved screenshot to /tmp/lelands_screenshot.png")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

if __name__ == "__main__":
    asyncio.run(research_lelands())
