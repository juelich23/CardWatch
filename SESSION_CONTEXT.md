# BulkBidding Session Context - December 27, 2024

## Project Overview
A multi-auction house aggregator that scrapes items from 19+ auction houses, displays them in a unified frontend, and allows bulk bidding.

## Tech Stack
- **Backend**: Python, FastAPI, SQLAlchemy (async), SQLite, Strawberry GraphQL
- **Frontend**: Next.js 14, React, Apollo Client, Tailwind CSS
- **Scrapers**: httpx, Playwright (for bot-protected sites like Heritage)
- **Market Value Estimation**: Claude Haiku API

---

## Key Changes Made This Session

### 1. Scraper Updates - Fetch ALL Item Types (Not Just Cards)

**Goal**: Previously scrapers only fetched graded cards. Now they fetch ALL items (memorabilia, autographs, jerseys, etc.)

**Files Modified**:

#### `/backend/app/scrapers/goldin_httpx.py`
- Removed `"item_type": ["Single Cards"]` filter from API payload
- Now fetches all item types from Goldin

#### `/backend/app/scrapers/fanatics.py` (lines 345-394)
- Removed subcategory-based filtering (was filtering by Sports Cards, TCG categories)
- Now uses simple pagination to fetch ALL live weekly items
- Changed from ~60 subcategory queries to unified query

```python
# Before: Filtered by subcategory
subcategories.append((f'subCategory1:"Sports Cards > {sport}" AND gradingService:"{grader}"', ...))

# After: No category filter
algolia_response = await self.fetch_algolia_items(client, api_key, page=page, hits_per_page=page_size, extra_filter=None)
```

#### `/backend/app/scrapers/pristine.py`
- Changed URL from `/auction/type/trading-cards` to `/auction/category/all`
- Updated `auction_external_id` from `"pristine-trading-cards"` to `"pristine-all"`

```python
# Before
self.trading_cards_url = f"{self.base_url}/auction/type/trading-cards"

# After
self.all_items_url = f"{self.base_url}/auction/category/all"
```

**Other scrapers already fetched all items**: Heritage, REA, Lelands, Classic Auctions, etc.

---

### 2. Market Value Caching in Database

**Goal**: Store LLM-generated market value estimates in DB to avoid repeated API calls.

**Files Modified**:

#### `/backend/app/models/auction.py`
Added new fields to `AuctionItem` model:
```python
market_value_low: Mapped[Optional[float]] = mapped_column(Float)
market_value_high: Mapped[Optional[float]] = mapped_column(Float)
market_value_avg: Mapped[Optional[float]] = mapped_column(Float)
market_value_confidence: Mapped[Optional[str]] = mapped_column(String(20))
market_value_notes: Mapped[Optional[str]] = mapped_column(String(1000))
market_value_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
```

#### `/backend/app/graphql/queries.py`
- Updated `market_value_estimate` resolver to check DB first
- If no cached value, calls LLM and saves result to DB

#### `/backend/app/graphql/types.py`
- Added market value fields to `AuctionItemType`
- Updated `auction_item_from_model` converter

---

### 3. Frontend Filters and Sorting

**Files Modified**:

#### `/frontend-nextjs/components/AuctionList.tsx`

**Item Type Filter** (lines 43-74):
```typescript
type ItemTypeFilter = '' | 'cards' | 'memorabilia' | 'autographs';

const isCardItem = (item: AuctionItem): boolean => {
  if (item.gradingCompany) return true;
  const cardKeywords = ['card', 'rookie', 'topps', 'panini', 'bowman', ...];
  return cardKeywords.some(kw => title.includes(kw));
};

const isMemorabiliaItem = (item: AuctionItem): boolean => { ... };
const isAutographItem = (item: AuctionItem): boolean => { ... };
```

**Best Value Sort** (lines 173-184):
- Sorts by lowest % of estimated market value
- Excludes items with $0 bid or no estimate

**Min/Max Price Filters** (lines 128-141):
```typescript
const [minPrice, setMinPrice] = useState('');
const [maxPrice, setMaxPrice] = useState('');
```

**Scroll to Top on Page Change** (lines 202-207):
```typescript
useEffect(() => {
  window.scrollTo(0, 0);
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}, [page]);
```

---

### 4. Market Value Badge Click Fix

#### `/frontend-nextjs/components/MarketValueBadge.tsx`
- Added `e.stopPropagation()` to prevent card selection when clicking estimate
- Shows current bid as percentage of estimated value

---

### 5. Auction Time UTC Fix

#### `/frontend-nextjs/components/AuctionCard.tsx` (lines 23-27)
```typescript
const formatTimeRemaining = (endTime?: string) => {
  if (!endTime) return 'Unknown';
  // Append 'Z' if no timezone indicator to treat as UTC
  const utcEndTime = endTime.includes('Z') || endTime.includes('+') ? endTime : endTime + 'Z';
  const end = new Date(utcEndTime);
  ...
};
```

---

### 6. Filter Ended Items

#### `/backend/app/graphql/queries.py`
When status is "Live", also filter out items where end_time has passed:
```python
if status == "Live":
    filters.append(AuctionItemModel.end_time > datetime.utcnow())
```

---

## Batch Scripts Created

### `/backend/populate_market_values.py`
Batch script to populate market value estimates for items without them:
- Processes items ordered by current_bid (highest value first)
- Includes retry logic for database locks
- Commits in batches to avoid contention

```bash
python populate_market_values.py --max 500 --batch 50
```

### `/backend/run_all_scrapers.py`
Runs all 19 scrapers sequentially:
```bash
python run_all_scrapers.py
```

---

## Scraper Results (Last Run)

| Auction House | Items |
|---------------|------:|
| Goldin | 3,859 |
| Fanatics | 2,399 |
| Greg Morris Cards | 1,500 |
| REA | 974 |
| RR Auction | 480 |
| Queen City Cards | 140 |
| Auction of Champions | 80 |
| Mile High | 50 |
| Heritage | 48 |
| Lelands | 47 |
| Clean Sweep | 32 |
| Pristine | 30 |
| Classic Auctions | 25 |
| Detroit City Sports | 25 |
| Sirius Sports | 25 |
| **Total** | **9,714** |

---

## Database Schema (Key Tables)

### auction_items
- id, auction_id, auction_house, external_id
- title, description, category, image_url
- current_bid, starting_bid, bid_count
- grading_company, grade, cert_number
- end_time, status, item_url
- market_value_low, market_value_high, market_value_avg
- market_value_confidence, market_value_notes, market_value_updated_at

---

## Common Commands

```bash
# Start backend
cd /Users/nickjuelich/Desktop/Code/BulkBidding/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Start frontend
cd /Users/nickjuelich/Desktop/Code/BulkBidding/frontend-nextjs
npm run dev

# Run all scrapers
python run_all_scrapers.py

# Populate market values
python populate_market_values.py --max 500

# Check DB item counts
sqlite3 auction_data.db "SELECT auction_house, COUNT(*) FROM auction_items WHERE status='Live' GROUP BY auction_house"
```

---

## Pending Tasks from Plan

There's a plan file at `/Users/nickjuelich/.claude/plans/rosy-wiggling-swing.md` for multi-user authentication with encrypted credential storage for placing bids. This was not implemented in this session.

---

## Important File Paths

- **Backend**: `/Users/nickjuelich/Desktop/Code/BulkBidding/backend/`
- **Frontend**: `/Users/nickjuelich/Desktop/Code/BulkBidding/frontend-nextjs/`
- **Scrapers**: `/backend/app/scrapers/*.py`
- **GraphQL**: `/backend/app/graphql/`
- **Models**: `/backend/app/models/`
- **Database**: `/backend/auction_data.db`
