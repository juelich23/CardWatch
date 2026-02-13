#!/usr/bin/env python3
"""
eBay Auction Scraper - Direct Web Scraping via Playwright
Fetches auction listings from eBay search results pages.
No API keys required. Uses Playwright to bypass eBay's bot detection.

Focuses on sports cards and collectibles categories.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from playwright.async_api import async_playwright, Browser, BrowserContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Auction, AuctionItem
from app.utils.sport_detection import detect_sport_from_item

logger = logging.getLogger(__name__)

# eBay search URL base
EBAY_SEARCH_URL = "https://www.ebay.com/sch/i.html"

# Search queries paired with categories for targeted scraping
# Category 212 = Sports Trading Cards, 213 = Non-Sport Trading Cards
SEARCH_CONFIGS = [
    {"query": "PSA graded card", "category": "212"},
    {"query": "BGS graded card", "category": "212"},
    {"query": "SGC graded card", "category": "212"},
    {"query": "basketball card", "category": "212"},
    {"query": "baseball card", "category": "212"},
    {"query": "football card", "category": "212"},
    {"query": "hockey card", "category": "212"},
    {"query": "soccer card", "category": "212"},
    {"query": "pokemon card graded", "category": "213"},
    {"query": "rookie card graded", "category": "212"},
    {"query": "sports card lot", "category": "212"},
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# JavaScript that runs in the browser to extract item data from search results.
# This is the most reliable approach - runs in the actual page context.
EXTRACT_ITEMS_JS = """() => {
    const results = [];
    const lis = document.querySelectorAll('ul.srp-results > li[data-listingid]');

    for (const li of lis) {
        const listingId = li.getAttribute('data-listingid');
        if (!listingId) continue;

        // Title
        const heading = li.querySelector('[role=heading]');
        let title = heading ? heading.textContent.trim() : '';
        // Clean trailing "Opens in a new window or tab" text
        title = title.replace(/Opens in a new (?:window|tab).*$/i, '').trim();
        if (!title || title.toLowerCase() === 'shop on ebay') continue;

        // Item URL
        const link = li.querySelector('a[href*="/itm/"]');
        const url = link ? link.href.split('?')[0] : '';

        // Price
        const priceEl = li.querySelector('.s-card__price');
        const priceText = priceEl ? priceEl.textContent.trim() : '';

        // Bids - look for text matching "N bid(s)"
        let bidText = '';
        const attrs = li.querySelector('.su-card-container__attributes');
        if (attrs) {
            const spans = attrs.querySelectorAll('.su-styled-text');
            for (const span of spans) {
                const t = span.textContent.trim();
                if (/\\d+\\s*bids?/i.test(t)) {
                    bidText = t;
                    break;
                }
            }
        }

        // Time left
        const timeLeftEl = li.querySelector('.s-card__time-left');
        const timeLeft = timeLeftEl ? timeLeftEl.textContent.trim() : '';

        // End time text (e.g., "(Today 05:15 PM)" or "(Feb 13, 2025 10:00 AM)")
        const timeEndEl = li.querySelector('.s-card__time-end');
        const timeEnd = timeEndEl ? timeEndEl.textContent.trim() : '';

        // Image
        const img = li.querySelector('img[src*="ebayimg"]');
        const imageUrl = img ? img.src : '';

        // Check for Buy It Now / fixed price indicators
        let hasBuyItNow = false;
        let hasBids = bidText !== '';
        if (attrs) {
            const fullText = attrs.textContent.toLowerCase();
            hasBuyItNow = fullText.includes('buy it now');
        }

        results.push({
            listingId,
            title,
            url,
            priceText,
            bidText,
            timeLeft,
            timeEnd,
            imageUrl,
            hasBuyItNow,
            hasBids,
        });
    }
    return results;
}"""


def _parse_time_left(time_str: str) -> Optional[datetime]:
    """Parse eBay's 'time left' string into an absolute datetime."""
    if not time_str:
        return None

    time_str = time_str.lower().strip()
    total_seconds = 0

    days = re.search(r'(\d+)\s*d', time_str)
    hours = re.search(r'(\d+)\s*h', time_str)
    minutes = re.search(r'(\d+)\s*m(?!o)', time_str)  # 'm' but not 'month'
    seconds = re.search(r'(\d+)\s*s', time_str)

    if days:
        total_seconds += int(days.group(1)) * 86400
    if hours:
        total_seconds += int(hours.group(1)) * 3600
    if minutes:
        total_seconds += int(minutes.group(1)) * 60
    if seconds:
        total_seconds += int(seconds.group(1))

    if total_seconds == 0:
        return None

    return datetime.utcnow() + timedelta(seconds=total_seconds)


def _parse_price(price_str: str) -> Optional[float]:
    """Parse a price string like '$12.50' or '$1,234.00' into a float."""
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_bid_count(bid_text: str) -> int:
    """Parse '3 bids' or '1 bid' into an integer."""
    if not bid_text:
        return 0
    match = re.search(r'(\d+)', bid_text)
    return int(match.group(1)) if match else 0


def _extract_grading_info(title: str) -> dict:
    """Extract grading company, grade, and cert number from title."""
    result = {"grading_company": None, "grade": None, "cert_number": None}

    grading_pattern = r'\b(PSA|BGS|Beckett|SGC|CGC)\s+(\d+(?:\.\d+)?)\b'
    match = re.search(grading_pattern, title, re.IGNORECASE)
    if match:
        company = match.group(1).upper()
        company_map = {"BGS": "Beckett", "BECKETT": "Beckett"}
        result["grading_company"] = company_map.get(company, match.group(1))
        result["grade"] = match.group(2)

    cert_match = re.search(r'#?\s*(\d{7,10})\b', title)
    if cert_match:
        result["cert_number"] = cert_match.group(1)

    return result


def _extract_category(title: str) -> Optional[str]:
    """Extract sport/category from title keywords."""
    categories = {
        "Basketball": ["Basketball", "NBA", "Kobe", "Jordan", "LeBron", "Luka"],
        "Football": ["Football", "NFL", "Brady", "Mahomes", "Burrow"],
        "Baseball": ["Baseball", "MLB", "Ohtani", "Trout", "Jeter"],
        "Hockey": ["Hockey", "NHL", "Gretzky", "McDavid"],
        "Soccer": ["Soccer", "FIFA", "Messi", "Ronaldo", "Haaland"],
        "Pokemon": ["Pokemon", "Pikachu", "Charizard"],
        "Magic The Gathering": ["Magic", "MTG"],
    }
    title_upper = title.upper()
    for cat, keywords in categories.items():
        if any(kw.upper() in title_upper for kw in keywords):
            return cat
    return None


class EbayScraper:
    """Scrape eBay auction listings via Playwright browser automation."""

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._pw = None
        # Load proxy settings
        from app.config import get_settings
        settings = get_settings()
        self._scraperapi_key = settings.scraperapi_key
        self._proxy_url = settings.proxy_url

    def _get_proxy_config(self) -> Optional[dict]:
        """Get proxy configuration for Playwright."""
        if self._scraperapi_key:
            return {
                "server": "http://proxy-server.scraperapi.com:8001",
                "username": "scraperapi",
                "password": self._scraperapi_key,
            }
        elif self._proxy_url:
            import urllib.parse
            parsed = urllib.parse.urlparse(self._proxy_url)
            config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username:
                config["username"] = parsed.username
            if parsed.password:
                config["password"] = parsed.password
            return config
        return None

    def _build_search_url(
        self, query: str, category: str = None, page: int = 1, items_per_page: int = 240,
    ) -> str:
        """Build an eBay search URL for auction-only listings, sorted by ending soonest."""
        params = {
            "_nkw": query,
            "LH_Auction": "1",
            "_sop": "1",
            "_ipg": str(items_per_page),
            "_pgn": str(page),
        }
        if category:
            params["_sacat"] = category
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{EBAY_SEARCH_URL}?{qs}"

    async def _ensure_browser(self):
        """Launch browser and visit eBay homepage to establish session cookies."""
        if self._browser is not None:
            return

        self._pw = await async_playwright().start()
        proxy = self._get_proxy_config()
        launch_kwargs = {
            "headless": True,
            "args": ["--ignore-certificate-errors"],
        }
        if proxy:
            launch_kwargs["proxy"] = proxy
            logger.info("eBay scraper using proxy")

        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )
        # Visit homepage first to get cookies and bypass challenge
        page = await self._context.new_page()
        try:
            await page.goto("https://www.ebay.com", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"eBay homepage visit failed: {e}")
        await page.close()

    async def _close_browser(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    async def _fetch_search_page(self, url: str) -> List[Dict]:
        """Fetch a search results page and extract item data via in-browser JS."""
        await self._ensure_browser()

        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check for challenge redirect
            if "challenge" in page.url.lower():
                logger.warning(f"eBay challenge detected at {page.url}")
                return []

            raw_items = await page.evaluate(EXTRACT_ITEMS_JS)
            return raw_items
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return []
        finally:
            await page.close()

    def _normalize_item(self, raw: Dict) -> Optional[Dict]:
        """Convert raw JS-extracted item dict to our DB format."""
        listing_id = raw.get("listingId", "")
        title = raw.get("title", "")
        if not listing_id or not title:
            return None

        # Auction-only filtering:
        # If item has "Buy It Now" but no bid info, it's fixed-price
        if raw.get("hasBuyItNow") and not raw.get("hasBids"):
            return None

        # Must have time left (auctions always show time remaining)
        time_left = raw.get("timeLeft", "")
        if not time_left:
            return None

        current_bid = _parse_price(raw.get("priceText", ""))
        bid_count = _parse_bid_count(raw.get("bidText", ""))
        end_time = _parse_time_left(time_left)

        grading_info = _extract_grading_info(title)
        category = _extract_category(title)
        sport = detect_sport_from_item(title, "", category or "")
        sport_value = sport.value if hasattr(sport, "value") else str(sport)

        image_url = raw.get("imageUrl", "")
        item_url = raw.get("url", "")

        return {
            "external_id": listing_id,
            "title": title[:500],
            "description": "",
            "category": category,
            "sport": sport_value,
            "grading_company": grading_info["grading_company"],
            "grade": grading_info["grade"],
            "cert_number": grading_info["cert_number"],
            "sub_category": category,
            "image_url": image_url or None,
            "current_bid": current_bid,
            "starting_bid": None,
            "bid_count": bid_count,
            "end_time": end_time,
            "status": "Live",
            "item_url": item_url or None,
            "lot_number": None,
            "raw_data": {
                "time_left_text": time_left,
                "price_text": raw.get("priceText", ""),
                "bid_text": raw.get("bidText", ""),
            },
        }

    async def scrape(self, db: AsyncSession, max_items: int = 5000) -> list:
        """Main entry point: scrape eBay auction listings and save to DB."""
        logger.info(f"Starting eBay web scrape (max_items={max_items})")

        all_items: Dict[str, dict] = {}

        try:
            for config in SEARCH_CONFIGS:
                if len(all_items) >= max_items:
                    break

                query = config["query"]
                category = config.get("category")
                logger.info(f"  Searching: '{query}' (cat={category})")

                page_num = 1
                max_pages = 5
                consecutive_empty = 0

                while page_num <= max_pages and len(all_items) < max_items:
                    url = self._build_search_url(query, category, page_num)

                    raw_items = await self._fetch_search_page(url)

                    if not raw_items:
                        consecutive_empty += 1
                        if consecutive_empty >= 2:
                            break
                        page_num += 1
                        await asyncio.sleep(3)
                        continue

                    consecutive_empty = 0
                    new_count = 0
                    for raw in raw_items:
                        item = self._normalize_item(raw)
                        if item and item["external_id"] not in all_items:
                            all_items[item["external_id"]] = item
                            new_count += 1

                    logger.info(
                        f"    Page {page_num}: {len(raw_items)} found, "
                        f"{new_count} new auctions (total: {len(all_items)})"
                    )

                    if new_count == 0:
                        break

                    page_num += 1
                    await asyncio.sleep(3)

        finally:
            await self._close_browser()

        items_list = list(all_items.values())[:max_items]
        logger.info(f"  Fetched {len(items_list)} unique eBay auction items")

        if not items_list:
            return []

        # Get or create auction record
        result = await db.execute(
            select(Auction).where(
                Auction.auction_house == "ebay",
                Auction.external_id == "ebay-auctions",
            )
        )
        auction = result.scalar_one_or_none()
        if not auction:
            auction = Auction(
                auction_house="ebay",
                external_id="ebay-auctions",
                title="eBay Auctions",
                status="active",
            )
            db.add(auction)
            await db.flush()

        # Upsert items
        saved = 0
        for item_data in items_list:
            try:
                result = await db.execute(
                    select(AuctionItem).where(
                        AuctionItem.auction_house == "ebay",
                        AuctionItem.external_id == item_data["external_id"],
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    for key, value in item_data.items():
                        if key != "external_id":
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                else:
                    db_item = AuctionItem(
                        auction_id=auction.id,
                        auction_house="ebay",
                        **item_data,
                    )
                    db.add(db_item)
                saved += 1
            except Exception as e:
                logger.error(f"    Error saving {item_data.get('external_id')}: {e}")

        await db.commit()
        logger.info(f"  Saved {saved} eBay items to database")
        return items_list

    async def health_check(self) -> dict:
        """Quick check that eBay search pages are reachable and parseable."""
        try:
            await self._ensure_browser()
            url = self._build_search_url("trading cards", "212", page=1, items_per_page=60)
            items = await self._fetch_search_page(url)
            await self._close_browser()
            return {
                "healthy": len(items) > 0,
                "message": f"Found {len(items)} items on test page",
            }
        except Exception as e:
            await self._close_browser()
            return {"healthy": False, "message": str(e)}


async def main():
    """Entry point for running the scraper standalone."""
    from app.database import init_db, get_db

    logging.basicConfig(level=logging.INFO)

    await init_db()
    scraper = EbayScraper()

    async for db in get_db():
        items = await scraper.scrape(db, max_items=500)
        print(f"\nScraping complete! Total items: {len(items)}")
        graded = [i for i in items if i.get("grading_company")]
        print(f"Items with grading data: {len(graded)}")
        break


if __name__ == "__main__":
    asyncio.run(main())
