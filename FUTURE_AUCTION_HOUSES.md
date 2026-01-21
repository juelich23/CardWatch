# Auction House Support Status

## Bidding Supported
Auction houses where we can place bids programmatically:
- [x] Goldin (browser automation)

## Scraping Supported
Auction houses where we can scrape item data:
- [x] Goldin
- [x] Fanatics Collect
- [x] Heritage Auctions
- [x] Pristine Auction
- [x] REA (Robert Edward Auctions)
- [x] ALT
- [x] Lelands
- [x] Classic Auctions
- [x] Memory Lane Inc
- [x] Mile High Card Company
- [x] Clean Sweep Auctions
- [x] RR Auction
- [x] Auction of Champions
- [x] Sirius Sports Auctions
- [x] Queen City Cards (AuctionNinja)
- [x] Greg Morris Cards

---

## Scrapers To Build

### Tier 1 - High Priority
All Tier 1 scrapers complete!

### Tier 2 - Medium Priority
| Auction House | Website | Status | Notes |
|--------------|---------|--------|-------|
| Greg Morris Cards | gregmorriscards.com/auctions | [x] Complete | SPA - needs refinement |
| Auction of Champions | auctionofchampions.com | [x] Complete | ~994 lots |
| Detroit City Sports | auctions.detroitcitysports.com | [x] Complete | Playwright scraper |
| Sirius Sports Cards | siriussportsauctions.com | [x] Complete | catalog.aspx |
| Queen City Cards | auctionninja.com/queen-city-cards | [x] Complete | AuctionNinja platform |
| VSA Auctions | vsaauctions.com | [x] Complete | Playwright scraper |
| Hunt Auctions | huntauctions.com | [x] Complete | Next auction Jan 2026 |
| Love of the Game Auctions | loveofthegameauctions.com | [x] Complete | Playwright scraper |

### Tier 3 - Other
| Auction House | Website | Status | Notes |
|--------------|---------|--------|-------|
| All-Star Cards | allstarcards.com | [ ] Pending | |
| CertifiedLink | certifiedlink.com | [ ] Pending | |
| BBCE Auctions | bbceauctions.com | [ ] Pending | |
| Bagger's Auctions | baggersauctions.com | [ ] Pending | |
| Collector Connection | collectorconnection.com | [ ] Pending | |
| Collector Investor Auctions | collectorinvestorauctions.com | [ ] Pending | |
| Create Auction | createauction.com | [ ] Pending | |
| Fat Apple Auctions | fatappleauctions.com | [ ] Pending | |
| The Football Gallery | footballgallery.com | [ ] Pending | |
| Game 7 Auctions | game7auctions.com | [ ] Pending | |
| MeiGray Auctions | meigray.com | [ ] Pending | Game-used jerseys |
| One of a Kind Collectibles | ooakc.com | [ ] Pending | |
| Rabbit Hole Auctions | rabbitholeauctions.com | [ ] Pending | |
| CardsHQ | cardshq.com | [ ] Pending | |

### Special Cases
| Auction House | Website | Status | Notes |
|--------------|---------|--------|-------|
| Independent eBay Sellers | ebay.com | [ ] Pending | Requires eBay API |

---

## Implementation Notes

### Scraper Requirements
Each scraper needs to extract:
- Item title
- Current bid / price
- Image URL
- Item URL
- End time
- Lot number (if available)
- Category (cards, memorabilia, etc.)
- Condition/grade (if available)

### Common Patterns
- Static HTML: Simple requests + BeautifulSoup
- JavaScript rendered: Playwright or find API
- API-based: Direct API calls (preferred)
- Algolia search: Many sites use Algolia

### Priority Order
1. Build Tier 1 scrapers first
2. Test and validate data quality
3. Move to Tier 2
4. Add Tier 3 as needed
