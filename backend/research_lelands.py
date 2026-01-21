"""
Research Lelands auction API
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def research_lelands():
    print("Researching Lelands auction platform...")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    page = await context.new_page()

    api_calls = []

    async def handle_request(request):
        url = request.url
        method = request.method
        if 'api' in url.lower() or method == 'POST':
            api_calls.append({
                'url': url,
                'method': method,
                'post_data': request.post_data
            })

    async def handle_response(response):
        url = response.url
        if 'api' in url.lower() or 'json' in response.headers.get('content-type', ''):
            for call in api_calls:
                if call['url'] == url:
                    try:
                        body = await response.text()
                        call['response'] = body[:2000]
                        call['content_type'] = response.headers.get('content-type', '')
                    except:
                        pass

    page.on('request', handle_request)
    page.on('response', handle_response)

    try:
        # Go to auction gallery
        print("\n1. Loading auction gallery...")
        await page.goto("https://auction.lelands.com/Lots/Gallery", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(3)

        # Get page structure
        print("\n2. Analyzing page structure...")
        structure = await page.evaluate("""
            () => {
                // Find lot/item containers
                const containers = document.querySelectorAll('[class*="lot"], [class*="item"], [class*="card"], [class*="product"]');
                const containerInfo = Array.from(containers).slice(0, 5).map(c => ({
                    tag: c.tagName,
                    classes: c.className,
                    childCount: c.children.length
                }));

                // Find images
                const images = document.querySelectorAll('img[src*="lot"], img[src*="item"], img[class*="lot"]');
                const imageInfo = Array.from(images).slice(0, 5).map(img => ({
                    src: img.src,
                    alt: img.alt
                }));

                // Find prices
                const prices = document.querySelectorAll('[class*="price"], [class*="bid"]');
                const priceInfo = Array.from(prices).slice(0, 5).map(p => ({
                    text: p.innerText,
                    classes: p.className
                }));

                return {containers: containerInfo, images: imageInfo, prices: priceInfo};
            }
        """)
        print(f"Containers found: {len(structure['containers'])}")
        print(f"Images found: {len(structure['images'])}")
        print(f"Prices found: {len(structure['prices'])}")

        # Get lot links
        lot_links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href*="lot"], a[href*="Lot"]'));
                return links.slice(0, 10).map(a => ({
                    href: a.href,
                    text: a.innerText.slice(0, 50)
                }));
            }
        """)
        print(f"\nLot links: {len(lot_links)}")
        for link in lot_links[:5]:
            print(f"  - {link['text']}: {link['href']}")

        # Look for pagination or infinite scroll
        pagination = await page.evaluate("""
            () => {
                const pagLinks = document.querySelectorAll('[class*="pag"], [aria-label*="page"]');
                const loadMore = document.querySelectorAll('[class*="load"]');
                return {
                    pagination: pagLinks.length,
                    loadMore: loadMore.length
                };
            }
        """)
        print(f"\nPagination elements: {pagination}")

        # Check for API calls
        print(f"\n3. API calls detected: {len(api_calls)}")
        for call in api_calls:
            if 'lot' in call['url'].lower() or 'auction' in call['url'].lower() or 'catalog' in call['url'].lower():
                print(f"\n  {call['method']} {call['url'][:100]}")
                if call.get('post_data'):
                    print(f"  Post data: {call['post_data'][:200]}")
                if call.get('response'):
                    print(f"  Response type: {call.get('content_type', 'unknown')}")
                    print(f"  Response preview: {call['response'][:300]}")

        # Try to click on first lot to see detail page API
        if lot_links:
            print(f"\n4. Loading first lot detail page...")
            await page.goto(lot_links[0]['href'], wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            detail_info = await page.evaluate("""
                () => {
                    const title = document.querySelector('h1, [class*="title"]');
                    const price = document.querySelector('[class*="price"], [class*="bid"]');
                    const image = document.querySelector('img[class*="lot"], img[class*="main"]');
                    return {
                        title: title ? title.innerText : null,
                        price: price ? price.innerText : null,
                        image: image ? image.src : null,
                        url: window.location.href
                    };
                }
            """)
            print(f"Detail page info: {json.dumps(detail_info, indent=2)}")

        # Print all API calls for analysis
        print("\n5. All API-like calls:")
        for call in api_calls[-20:]:
            print(f"  {call['method']} {call['url'][:120]}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()

if __name__ == "__main__":
    asyncio.run(research_lelands())
