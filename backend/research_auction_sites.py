"""
Research auction house websites to determine scraping approach
"""
import asyncio
import json
from playwright.async_api import async_playwright

SITES_TO_RESEARCH = [
    ("Lelands", "https://lelands.com"),
    ("Classic Auctions", "https://classicauctions.net"),
    ("Memory Lane Inc", "https://www.memorylaneinc.com"),
    ("Mile High Card Company", "https://www.milehighcardco.com"),
    ("Clean Sweep Auctions", "https://www.cleansweepauctions.com"),
    ("RR Auction", "https://www.rrauction.com"),
]

async def research_site(name: str, url: str):
    """Research a single auction site"""
    print(f"\n{'='*60}")
    print(f"Researching: {name} ({url})")
    print('='*60)

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    page = await context.new_page()

    api_calls = []
    algolia_found = False

    # Intercept network requests
    async def handle_request(request):
        nonlocal algolia_found
        url = request.url
        if 'api' in url.lower() or 'graphql' in url.lower():
            api_calls.append({'url': url, 'method': request.method})
        if 'algolia' in url.lower():
            algolia_found = True
            api_calls.append({'url': url, 'method': request.method, 'type': 'algolia'})

    page.on('request', handle_request)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Get page title
        title = await page.title()
        print(f"Page Title: {title}")

        # Check for common frameworks/libraries
        frameworks = await page.evaluate("""
            () => {
                const found = [];
                if (window.React) found.push('React');
                if (window.Vue) found.push('Vue');
                if (window.angular) found.push('Angular');
                if (window.jQuery || window.$) found.push('jQuery');
                if (window.algoliasearch) found.push('Algolia');
                if (window.__NEXT_DATA__) found.push('Next.js');
                if (window.__NUXT__) found.push('Nuxt.js');
                return found;
            }
        """)
        print(f"Frameworks detected: {frameworks if frameworks else 'None detected'}")

        # Look for auction/item links
        item_links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                const auctionLinks = links.filter(a => {
                    const href = a.href.toLowerCase();
                    return href.includes('lot') || href.includes('item') ||
                           href.includes('auction') || href.includes('bid');
                }).slice(0, 10);
                return auctionLinks.map(a => ({text: a.innerText.slice(0, 50), href: a.href}));
            }
        """)
        print(f"\nSample auction links found: {len(item_links)}")
        for link in item_links[:5]:
            print(f"  - {link['text']}: {link['href'][:80]}")

        # Check for pagination patterns
        pagination = await page.evaluate("""
            () => {
                const pagers = document.querySelectorAll('[class*="pag"], [class*="page"], .pagination, nav[aria-label*="pag"]');
                return pagers.length > 0;
            }
        """)
        print(f"Pagination found: {pagination}")

        # Report API calls
        print(f"\nAPI/Network calls detected: {len(api_calls)}")
        print(f"Algolia detected: {algolia_found}")
        for call in api_calls[:10]:
            print(f"  - {call['method']} {call['url'][:100]}")

        # Try to find auction listing page
        nav_links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a, button'));
                return links.filter(el => {
                    const text = el.innerText.toLowerCase();
                    return text.includes('auction') || text.includes('catalog') ||
                           text.includes('browse') || text.includes('current');
                }).map(el => ({text: el.innerText.slice(0, 30), href: el.href || 'button'})).slice(0, 5);
            }
        """)
        print(f"\nNavigation links:")
        for link in nav_links:
            print(f"  - {link['text']}: {link['href'][:60] if link['href'] != 'button' else 'button'}")

        # Summary
        print(f"\n--- SUMMARY for {name} ---")
        if algolia_found:
            print("✅ Uses Algolia - can use Algolia API for fast scraping")
        elif api_calls:
            print(f"✅ Has API endpoints - check network tab for details")
        else:
            print("⚠️ May need HTML parsing or Playwright")

        return {
            "name": name,
            "url": url,
            "frameworks": frameworks,
            "algolia": algolia_found,
            "api_calls": len(api_calls),
            "item_links": len(item_links)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"name": name, "url": url, "error": str(e)}
    finally:
        await browser.close()
        await p.stop()


async def main():
    results = []
    for name, url in SITES_TO_RESEARCH:
        try:
            result = await research_site(name, url)
            results.append(result)
        except Exception as e:
            print(f"Failed to research {name}: {e}")
            results.append({"name": name, "url": url, "error": str(e)})

    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    for r in results:
        status = "✅" if not r.get("error") else "❌"
        algolia = "Algolia" if r.get("algolia") else ""
        apis = f"{r.get('api_calls', 0)} APIs" if r.get('api_calls') else ""
        print(f"{status} {r['name']}: {algolia} {apis}")

if __name__ == "__main__":
    asyncio.run(main())
