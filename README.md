# BulkBidding - Auction Aggregator

High-performance auction aggregation platform with bulk bidding capabilities.

## Features

- **Multi-Auction House Support**: Goldin, Fanatics, Pristine, REA (Heritage coming soon)
- **GraphQL API**: Flexible queries with Strawberry GraphQL
- **Bulk Bidding**: Place multiple bids simultaneously
- **Market Value Estimates**: Claude AI-powered valuations
- **Advanced Filtering**: Search, filter, and sort across all auctions

## Tech Stack

### Backend
- **FastAPI**: High-performance async Python web framework
- **Strawberry GraphQL**: Type-safe GraphQL API
- **SQLAlchemy 2.0**: Async ORM for database operations
- **Playwright/HTTPX**: Scraping (Playwright for JS-heavy sites, HTTPX for APIs)
- **SQLite**: Database (via aiosqlite)

### Frontend
- **Next.js 16**: React framework with App Router
- **React 19**: Modern UI framework
- **TypeScript 5**: Type-safe development
- **Apollo Client**: GraphQL data fetching
- **TailwindCSS 4**: Utility-first styling

## Quick Start

### Backend Setup

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Start the API server
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- GraphQL Playground: http://localhost:8000/graphql

### Frontend Setup

```bash
cd frontend-nextjs

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:3000

## Configuration

Edit `backend/.env`:

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./auction_data.db

# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key
ALT_API_KEY=your_alt_api_key

# Goldin Credentials (for bidding)
GOLDIN_EMAIL=your_email@example.com
GOLDIN_PASSWORD=your_password
```

## Usage

### Loading Auction Data

```bash
cd backend
python reload_all_auctions.py --goldin --fanatics --pristine --rea
```

### GraphQL API

**Query Auction Items**
```graphql
query {
  auctionItems(page: 1, pageSize: 50, status: "active") {
    items {
      id
      title
      currentBid
      auctionHouse
      endTime
    }
    totalCount
    hasMore
  }
}
```

**Place a Bid**
```graphql
mutation {
  placeBid(itemId: 123, bidAmount: 100.00, maxBid: 150.00) {
    success
    message
    bid {
      id
      amount
      status
    }
  }
}
```

**Get Market Value Estimate**
```graphql
query {
  marketValueEstimate(itemId: 123) {
    estimatedValue
    confidence
    reasoning
  }
}
```

## Scrapers

| Auction House | Method | Status |
|--------------|--------|--------|
| Goldin | HTTPX (API) | Working |
| Fanatics | Algolia + GraphQL | Working |
| Pristine | HTML parsing | Working |
| REA | HTML + Alpine.js | Working |
| Heritage | TBD | Planned |

## Roadmap

- [x] Goldin scraper
- [x] Fanatics scraper
- [x] Pristine scraper
- [x] REA scraper
- [x] GraphQL API
- [x] Market value estimation (Claude AI)
- [ ] Heritage scraper
- [ ] Real bidding integration with auction houses
- [ ] WebSocket for real-time updates
- [ ] User accounts and saved credentials
- [ ] Watchlists and notifications
- [ ] Bid sniping

## Legal Notice

This tool is for educational purposes. Always review and comply with the Terms of Service of each auction house. Automated bidding may be prohibited by some platforms.

## License

MIT
