# CardWatch - Sports Card Auction Aggregator

A high-performance auction aggregation platform for sports card collectors. Browse and track auction items from multiple auction houses in one place.

**Live Site:** [https://cardwatch.vercel.app](https://cardwatch.vercel.app)

## Features

- **Multi-Auction House Support**: Goldin, Fanatics, Pristine, Heritage, CardHobby
- **AI-Powered Search**: Natural language search powered by Claude AI
- **Advanced Filtering**: Filter by auction house, sport, item type, price range
- **Watchlist**: Save items to track across auction houses
- **Market Value Estimates**: AI-powered card valuations
- **Real-Time Updates**: Automated scraping keeps prices current
- **Mobile-Friendly**: Responsive design for browsing on any device

## Tech Stack

### Backend
- **FastAPI**: High-performance async Python web framework
- **Strawberry GraphQL**: Type-safe GraphQL API
- **SQLAlchemy 2.0**: Async ORM with PostgreSQL
- **APScheduler**: Automated scraping jobs
- **HTTPX**: Async HTTP client for API scraping

### Frontend
- **Next.js 15**: React framework with App Router
- **React 19**: Modern UI with Server Components
- **TypeScript 5**: Type-safe development
- **Apollo Client**: GraphQL data fetching with caching
- **TailwindCSS 4**: Utility-first styling
- **Framer Motion**: Smooth animations

### Infrastructure
- **Vercel**: Frontend hosting with edge functions
- **Railway**: Backend hosting with auto-deployments
- **Supabase**: PostgreSQL database with connection pooling

## Local Development

### Backend Setup

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the API server
uvicorn app.main:app --reload --port 8000
```

- API Docs: http://localhost:8000/docs
- GraphQL Playground: http://localhost:8000/graphql

### Frontend Setup

```bash
cd frontend-nextjs

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration

# Start development server
npm run dev
```

Frontend: http://localhost:3000

## GraphQL API

### Query Auction Items

```graphql
query {
  auctionItems(page: 1, pageSize: 50, status: "Live") {
    items {
      id
      title
      currentBid
      auctionHouse
      endTime
      sport
      imageUrl
    }
    total
  }
}
```

### Toggle Watchlist

```graphql
mutation {
  toggleWatch(itemId: 123) {
    success
    message
  }
}
```

## Supported Auction Houses

| Auction House | Sports | Update Frequency |
|--------------|--------|------------------|
| Goldin | All | Every 30 min |
| Fanatics | All | Every 30 min |
| Pristine | All | Every 30 min |
| Heritage | All | Every 60 min |
| CardHobby | All | Every 30 min |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT
