#!/usr/bin/env python3
"""
Heritage Auctions Scraper
Fetches auction items from Heritage Auctions (ha.com) sports cards section
Uses Playwright with Firefox to bypass bot detection
Supports proxy configuration for better access
"""

import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, init_db
from app.models import Auction, AuctionItem
from app.scrapers.base import HealthCheckResult
from app.utils.sport_detection import detect_sport_from_item
from app.config import get_settings


class HeritageScraper:
    def __init__(self):
        self.base_url = "https://sports.ha.com"
        self.main_url = "https://www.ha.com"
        settings = get_settings()
        self.proxy_url = settings.proxy_url
        self.scraperapi_key = settings.scraperapi_key

    def extract_grading_info(self, title: str) -> dict:
        """Extract grading company, grade, and cert number from title"""
        result = {
            'grading_company': None,
            'grade': None,
            'cert_number': None
        }

        # PSA pattern - e.g., "PSA NM-MT 8", "PSA Gem Mint 10", "PSA 10"
        psa_patterns = [
            r'\bPSA\s+(?:(?:GEM\s+)?(?:MINT|NM-MT|NM|EX-MT|EX|VG-EX|VG|GOOD|FAIR|POOR)(?:\s*\+)?)\s*(\d+(?:\.\d+)?)\b',
            r'\bPSA\s+(\d+(?:\.\d+)?)\b'
        ]
        for pattern in psa_patterns:
            psa_match = re.search(pattern, title, re.IGNORECASE)
            if psa_match:
                result['grading_company'] = 'PSA'
                result['grade'] = psa_match.group(1)
                return result

        # BGS/Beckett pattern
        bgs_pattern = r'\b(BGS|Beckett|BCCG)\s+(?:(?:GEM\s+)?(?:MINT|PRISTINE)\s+)?([\d.]+)\b'
        bgs_match = re.search(bgs_pattern, title, re.IGNORECASE)
        if bgs_match:
            company = bgs_match.group(1)
            company_map = {'BGS': 'Beckett', 'BECKETT': 'Beckett', 'BCCG': 'Beckett'}
            result['grading_company'] = company_map.get(company.upper(), 'Beckett')
            result['grade'] = bgs_match.group(2)
            return result

        # SGC pattern
        sgc_pattern = r'\bSGC\s+([\d.]+)\b'
        sgc_match = re.search(sgc_pattern, title, re.IGNORECASE)
        if sgc_match:
            result['grading_company'] = 'SGC'
            result['grade'] = sgc_match.group(1)
            return result

        # CGC pattern
        cgc_pattern = r'\bCGC\s+([\d.]+)\b'
        cgc_match = re.search(cgc_pattern, title, re.IGNORECASE)
        if cgc_match:
            result['grading_company'] = 'CGC'
            result['grade'] = cgc_match.group(1)
            return result

        return result

    def extract_category(self, title: str) -> Optional[str]:
        """Extract sport/category from title"""
        categories = {
            'Basketball': ['Basketball', 'NBA', 'Jordan', 'Kobe', 'LeBron', 'Curry', 'Fleer'],
            'Football': ['Football', 'NFL', 'Brady', 'Mahomes'],
            'Baseball': ['Baseball', 'MLB', 'Topps', 'Ruth', 'Mantle', 'Griffey', 'Trout', 'T206', 'T205', 'T207'],
            'Hockey': ['Hockey', 'NHL', 'Gretzky', 'Lemieux'],
            'Soccer': ['Soccer', 'MLS', 'Messi', 'Ronaldo'],
            'Golf': ['Golf', 'PGA', 'Tiger Woods'],
            'Boxing': ['Boxing', 'Muhammad Ali', 'Tyson', 'Ali'],
            'Racing': ['Racing', 'NASCAR', 'F1'],
        }

        title_upper = title.upper()
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword.upper() in title_upper:
                    return category

        return 'Sports'  # Default for Heritage sports

    def _get_proxy_config(self) -> Optional[Dict]:
        """Get proxy configuration if available"""
        if self.scraperapi_key:
            # ScraperAPI proxy format
            return {
                "server": "http://proxy-server.scraperapi.com:8001",
                "username": "scraperapi",
                "password": self.scraperapi_key,
            }
        elif self.proxy_url:
            # Parse proxy URL (format: http://user:pass@host:port or http://host:port)
            import urllib.parse
            parsed = urllib.parse.urlparse(self.proxy_url)
            proxy_config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username:
                proxy_config["username"] = parsed.username
            if parsed.password:
                proxy_config["password"] = parsed.password
            return proxy_config
        return None

    async def scrape_with_scraperapi(self, max_items: int = 500) -> List[Dict]:
        """Scrape Heritage using ScraperAPI's render endpoint"""
        import httpx
        from bs4 import BeautifulSoup

        if not self.scraperapi_key:
            print("   ScraperAPI key not configured")
            return []

        items = []
        seen_ids = set()
        pages_scraped = 0
        max_pages = max(1, max_items // 48)  # ~48 items per page

        async with httpx.AsyncClient(timeout=120.0) as client:
            while len(items) < max_items and pages_scraped < max_pages:
                offset = pages_scraped * 48
                # Heritage open auctions URL
                target_url = f'{self.base_url}/c/search-results.zx?ic4=Auctions-Open&N=790+231&No={offset}&Nrpp=48'

                # ScraperAPI endpoint with render=true for JavaScript
                api_url = f"http://api.scraperapi.com?api_key={self.scraperapi_key}&url={target_url}&render=true&country_code=us"

                print(f"   Fetching page {pages_scraped + 1} via ScraperAPI...")

                try:
                    response = await client.get(api_url)
                    if response.status_code != 200:
                        print(f"   Error: ScraperAPI returned {response.status_code}")
                        break

                    html = response.text
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find auction item links
                    page_items = []
                    for link in soup.find_all('a', href=re.compile(r'/a/\d+-\d+')):
                        href = link.get('href', '')
                        if not href or 'auction-home' in href:
                            continue

                        # Extract auction ID and lot number
                        url_match = re.search(r'/a/(\d+)-(\d+)', href)
                        if not url_match:
                            continue

                        auction_id = url_match.group(1)
                        lot_number = url_match.group(2)
                        item_id = f"{auction_id}-{lot_number}"

                        if item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)

                        # Find the item container
                        container = link.find_parent(['div', 'article'])
                        if not container:
                            continue

                        text = container.get_text(' ', strip=True)

                        # Extract title
                        title = None
                        title_elem = container.find(['h3', 'h4', 'a'], class_=re.compile(r'title|name', re.I))
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                        if not title or len(title) < 20:
                            # Try link text
                            title = link.get_text(strip=True)
                        if not title or len(title) < 20:
                            continue

                        # Extract bid amount
                        bid_match = re.search(r'\$([0-9,]+)', text)
                        current_bid = float(bid_match.group(1).replace(',', '')) if bid_match else None

                        # Extract image
                        img = container.find('img', src=re.compile(r'heritagestatic'))
                        img_src = None
                        if img:
                            img_src = img.get('src') or img.get('data-src')
                            if img_src:
                                img_src = re.sub(r'w=\d+', 'w=400', img_src)
                                img_src = re.sub(r'h=\d+', 'h=600', img_src)

                        # Extract end time
                        end_time_str = None
                        end_match = re.search(r'[Ee]nds?\s+([A-Za-z]{3}\s+\d{1,2},?\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)', text)
                        if end_match:
                            end_time_str = end_match.group(1)

                        # Make URL absolute
                        full_url = href if href.startswith('http') else f"{self.base_url}{href}"

                        page_items.append({
                            'title': title[:400],
                            'href': full_url,
                            'auctionId': auction_id,
                            'lotNumber': lot_number,
                            'currentBid': current_bid,
                            'estimate': None,
                            'imgSrc': img_src,
                            'endTime': end_time_str
                        })

                    items.extend(page_items)
                    pages_scraped += 1
                    print(f"   Page {pages_scraped}: Found {len(page_items)} items (total: {len(items)})")

                    if len(page_items) == 0:
                        print("   No more items found, stopping")
                        break

                except Exception as e:
                    print(f"   Error fetching page: {e}")
                    break

        return items[:max_items]

    async def scrape_with_playwright(self, max_items: int = 500) -> List[Dict]:
        """Scrape Heritage using Playwright with Firefox"""
        from playwright.async_api import async_playwright

        items = []
        seen_ids = set()

        async with async_playwright() as p:
            # Launch Firefox (non-headless to bypass bot detection)
            # Note: Don't use proxy for Heritage - ScraperAPI requires ultra_premium
            # and the local browser approach works well
            browser = await p.firefox.launch(headless=False)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
                viewport={'width': 1920, 'height': 1080},
            )
            page = await context.new_page()

            try:
                # Navigate through heritage properly to set cookies
                print("   Navigating to Heritage...")
                await page.goto(self.main_url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)

                pages_scraped = 0
                items_per_page = 48
                max_pages = max(1, (max_items // items_per_page) + 1)

                while len(items) < max_items and pages_scraped < max_pages:
                    # Use the working live auctions URL with pagination
                    # page=48~{page_num} means 48 items per page, page number
                    page_num = pages_scraped + 1
                    search_url = f'{self.base_url}/c/search/results.zx?si=2&dept=3923&live_state=5318&item_type_sports=3927&mode=live&page={items_per_page}~{page_num}&ic4=Refine-SportsItemType-102615'

                    print(f"   Loading page {page_num}...")
                    await page.goto(search_url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(3)
                    # Scroll to trigger lazy loading of images
                    for scroll_pos in [500, 1000, 1500, 2000, 3000]:
                        await page.evaluate(f'window.scrollTo(0, {scroll_pos})')
                        await asyncio.sleep(0.5)

                    # Extract items from current page
                    page_items = await page.evaluate('''() => {
                        const items = [];
                        const seen = new Set();

                        // Find all links to auction items
                        document.querySelectorAll('a[href*=".s"], a[href*="/itm/"]').forEach(link => {
                            const href = link.href;

                            // Must be an item link
                            if (!href.includes('/a/') && !href.includes('/itm/')) return;
                            if (href.includes('auction-home') || href.includes('browse.zx')) return;

                            // IMPORTANT: Skip sample items and "other results" - these are sold items
                            // shown as recommendations, not live auctions
                            if (href.includes('SampleItem') || href.includes('OtherResults')) return;

                            // Extract auction ID and lot number from URL
                            const urlMatch = href.match(/\\/a\\/(\\d+)-(\\d+)/);
                            if (!urlMatch) return;

                            const auctionId = urlMatch[1];
                            const lotNumber = urlMatch[2];
                            const itemId = `${auctionId}-${lotNumber}`;

                            // Skip if we've already seen this item
                            if (seen.has(itemId)) return;
                            seen.add(itemId);

                            // Find the item container - Heritage uses 'promo-item' or 'item-block' classes
                            let container = null;
                            let el = link;
                            for (let i = 0; i < 10 && el; i++) {
                                el = el.parentElement;
                                if (!el) break;

                                const className = el.className || '';
                                // Found item container
                                if (className.includes('promo-item') || className.includes('item-block')) {
                                    container = el;
                                    break;
                                }
                            }

                            // Fallback: find parent with exactly 1 image
                            if (!container) {
                                el = link;
                                for (let i = 0; i < 8 && el; i++) {
                                    el = el.parentElement;
                                    if (!el) break;

                                    const imgs = el.querySelectorAll('img[src*="heritagestatic"]');
                                    const links = el.querySelectorAll('a[href*="/a/"]');
                                    // Good container has 1 image and reasonable number of links
                                    if (imgs.length === 1 && links.length >= 1 && links.length <= 5) {
                                        container = el;
                                        break;
                                    }
                                }
                            }

                            if (!container) return;

                            const text = container.innerText || '';

                            // Get title - look for substantial text in the container
                            let title = '';
                            // First try the link text
                            const linkText = link.innerText?.trim();
                            if (linkText && linkText.length > 25 && !linkText.includes('Bid Now')) {
                                title = linkText;
                            }
                            // Try finding title in container spans/links
                            if (!title || title.length < 25) {
                                const textEls = container.querySelectorAll('a[href*="/a/"] span, a[href*="/itm/"], span');
                                for (const el of textEls) {
                                    const t = el.innerText?.trim();
                                    if (t && t.length > 30 && !t.includes('$') && !t.startsWith('Lot') && !t.includes('Bid')) {
                                        title = t;
                                        break;
                                    }
                                }
                            }
                            // Last resort - parse container text
                            if (!title || title.length < 25) {
                                const lines = text.split('\\n')
                                    .map(l => l.trim())
                                    .filter(l => l.length > 30 && !l.includes('$') && !l.startsWith('Lot') && !l.startsWith('Guide'));
                                title = lines[0] || '';
                            }

                            // Skip if no valid title
                            if (!title || title.length < 20) return;
                            if (title.startsWith('Guide Value')) return;

                            // Parse bid and estimate
                            const bidMatch = text.match(/Current Bid[:\\s]*\\$([\\d,]+)/i) || text.match(/\\$([\\d,]+)/);
                            const estimateMatch = text.match(/(?:Guide Value|Estimate)[:\\s]*\\$([\\d,]+)/i);

                            // Parse end time - Heritage shows "Ends: Dec 28, 2024 10:00 PM CT" or similar
                            let endTimeStr = null;
                            const endTimeMatch = text.match(/Ends?[:\\s]+([A-Za-z]{3}\\s+\\d{1,2},?\\s+\\d{4}\\s+\\d{1,2}:\\d{2}(?:\\s*[AP]M)?(?:\\s*[A-Z]{2,3})?)/i);
                            if (endTimeMatch) {
                                endTimeStr = endTimeMatch[1];
                            }
                            // Also try relative time like "Ends in 3d 4h"
                            const relativeMatch = text.match(/Ends?\\s+in\\s+(\\d+)d\\s*(\\d+)h/i);
                            if (!endTimeStr && relativeMatch) {
                                const days = parseInt(relativeMatch[1]);
                                const hours = parseInt(relativeMatch[2]);
                                const endDate = new Date();
                                endDate.setDate(endDate.getDate() + days);
                                endDate.setHours(endDate.getHours() + hours);
                                endTimeStr = endDate.toISOString();
                            }

                            // Find image within THIS container only
                            let imgSrc = null;
                            const img = container.querySelector('img[src*="heritagestatic"]');
                            if (img) {
                                let src = img.src || img.getAttribute('data-src');
                                if (src) {
                                    // Upgrade to larger image size
                                    src = src.replace(/w=\\d+/, 'w=400').replace(/h=\\d+/, 'h=600');
                                    imgSrc = src;
                                }
                            }

                            items.push({
                                title: title.substring(0, 400),
                                href: href,
                                auctionId: auctionId,
                                lotNumber: lotNumber,
                                currentBid: bidMatch ? parseFloat(bidMatch[1].replace(/,/g, '')) : null,
                                estimate: estimateMatch ? parseFloat(estimateMatch[1].replace(/,/g, '')) : null,
                                imgSrc: imgSrc,
                                endTime: endTimeStr
                            });
                        });

                        return items;
                    }''')

                    # Add unique items (dedup by auction-lot ID)
                    new_items_count = 0
                    for item in page_items:
                        item_id = f"{item['auctionId']}-{item['lotNumber']}"
                        if item_id not in seen_ids:
                            seen_ids.add(item_id)
                            items.append(item)
                            new_items_count += 1

                    pages_scraped += 1
                    print(f"   Page {pages_scraped}: Found {len(page_items)} items, {new_items_count} new (total: {len(items)})")

                    # Stop if no new items found (reached end or all duplicates)
                    if new_items_count == 0:
                        print("   No new items found, stopping pagination")
                        break

                    if len(items) >= max_items:
                        break

                    # Small delay before next page
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"   Error during scraping: {e}")
            finally:
                await browser.close()

        return items[:max_items]

    async def scrape(self, db: AsyncSession, max_items: int = 2500, max_pages: int = 60) -> list:
        """Main scraping function"""
        print("🔍 Fetching items from Heritage Auctions...")

        # Use Playwright - it works reliably with the live auctions URL
        # ScraperAPI requires ultra_premium for Heritage which is paid
        raw_items = await self.scrape_with_playwright(max_items)

        print(f"✅ Scraped {len(raw_items)} items from Heritage")

        if not raw_items:
            print("⚠️ No items found from Heritage")
            return []

        # Normalize items
        normalized_items = []
        for item in raw_items:
            title = item.get('title', '')
            grading_info = self.extract_grading_info(title)
            category = self.extract_category(title)

            # Generate external ID from auction + lot
            auction_id = item.get('auctionId', '')
            lot_number = item.get('lotNumber', '')
            external_id = f"{auction_id}-{lot_number}" if auction_id and lot_number else item.get('href', '')[-50:]

            # Parse end time
            end_time = None
            end_time_str = item.get('endTime')
            if end_time_str:
                try:
                    # Try ISO format first (from relative time calculation)
                    if 'T' in end_time_str:
                        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    else:
                        # Parse formats like "Dec 28, 2024 10:00 PM CT"
                        from dateutil import parser as date_parser
                        end_time = date_parser.parse(end_time_str)
                except Exception as e:
                    print(f"   Warning: Could not parse end time '{end_time_str}': {e}")

            # If no end time was extracted, set a default of 7 days from now
            # Heritage auctions typically run 1-2 weeks, so this is a reasonable default
            if end_time is None:
                from datetime import timedelta
                end_time = datetime.utcnow() + timedelta(days=7)

            # Detect sport from item content
            sport = detect_sport_from_item(title, None, category).value

            normalized = {
                "external_id": external_id,
                "lot_number": lot_number,
                "cert_number": grading_info['cert_number'],
                "sub_category": category,
                "grading_company": grading_info['grading_company'],
                "grade": grading_info['grade'],
                "title": title[:500],
                "description": None,
                "category": category,
                "sport": sport,
                "image_url": item.get('imgSrc'),
                "current_bid": item.get('currentBid'),
                "starting_bid": item.get('estimate'),
                "bid_count": 0,
                "end_time": end_time,
                "status": "Live",
                "item_url": item.get('href'),
                "raw_data": {
                    "auction_id": auction_id,
                    "estimate": item.get('estimate')
                }
            }
            normalized_items.append(normalized)

        # Create or update auction
        print(f"\n📦 Creating/updating auction record...")
        auction_external_id = "heritage-sports"

        result = await db.execute(
            select(Auction).where(
                Auction.auction_house == "heritage",
                Auction.external_id == auction_external_id
            )
        )
        auction = result.scalar_one_or_none()

        if not auction:
            auction = Auction(
                auction_house="heritage",
                external_id=auction_external_id,
                title="Heritage Auctions - Sports",
                status="active"
            )
            db.add(auction)
            await db.flush()

        print(f"✅ Auction ID: {auction.id}")

        # Save items to database
        print(f"\n💾 Saving {len(normalized_items)} items to database...")

        for item_data in normalized_items:
            result = await db.execute(
                select(AuctionItem).where(
                    AuctionItem.auction_house == "heritage",
                    AuctionItem.external_id == item_data["external_id"]
                )
            )
            existing_item = result.scalar_one_or_none()

            if existing_item:
                for key, value in item_data.items():
                    if key not in ['external_id', 'auction_house']:
                        setattr(existing_item, key, value)
                existing_item.updated_at = datetime.utcnow()
            else:
                item = AuctionItem(
                    auction_id=auction.id,
                    auction_house="heritage",
                    **item_data
                )
                db.add(item)

        await db.commit()
        print(f"✅ Saved {len(normalized_items)} items to database")

        # Count items with grading data
        graded_items = [item for item in normalized_items if item.get('grading_company')]
        print(f"   Items with grading data: {len(graded_items)}")

        return normalized_items

    async def health_check(self) -> HealthCheckResult:
        """Check if Heritage Auctions is reachable via Playwright"""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=False)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
                )
                page = await context.new_page()

                try:
                    await page.goto(self.main_url, wait_until='domcontentloaded', timeout=15000)
                    await page.goto(self.base_url, wait_until='domcontentloaded', timeout=15000)
                    title = await page.title()

                    if 'Heritage' in title or 'Sports' in title:
                        return HealthCheckResult(
                            healthy=True,
                            message="Heritage Auctions is reachable via Playwright",
                            details={"title": title}
                        )
                    return HealthCheckResult(
                        healthy=False,
                        message="Heritage page loaded but title unexpected",
                        details={"title": title}
                    )
                finally:
                    await browser.close()

        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Heritage Auctions unreachable: {str(e)}",
                details={"error": str(e)}
            )


async def main():
    """Entry point for running the scraper"""
    await init_db()

    scraper = HeritageScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=100, max_pages=3)

        print(f"\n✅ Scraping complete!")
        print(f"   Total items: {len(items)}")


if __name__ == "__main__":
    asyncio.run(main())
