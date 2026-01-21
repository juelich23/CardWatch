# Scraper Scheduler

The scheduler runs scrapers on a recurring basis to keep auction data fresh.

## Quick Start

### Manual Job Control (Recommended for Development)

```bash
# Start the backend
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Enable scrapers via API
curl -X POST "http://localhost:8000/api/scheduler/jobs/cardhobby/enable"
curl -X POST "http://localhost:8000/api/scheduler/jobs/goldin/enable"

# Trigger immediate run
curl -X POST "http://localhost:8000/api/scheduler/jobs/cardhobby/run"

# Check status
curl http://localhost:8000/api/scheduler/status
```

### Auto-Start All Jobs (Production)

Set environment variable before starting:

```bash
export ENABLE_SCHEDULER=true
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This will automatically enable all scrapers with their default intervals on startup.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scheduler/status` | GET | Scheduler status and active jobs |
| `/api/scheduler/jobs` | GET | List all active scheduled jobs |
| `/api/scheduler/jobs/available` | GET | List available scrapers to enable |
| `/api/scheduler/jobs/{id}/enable` | POST | Enable a scraper job |
| `/api/scheduler/jobs/{id}/enable?interval_minutes=15` | POST | Enable with custom interval |
| `/api/scheduler/jobs/{id}/disable` | POST | Remove a job from schedule |
| `/api/scheduler/jobs/{id}/run` | POST | Trigger immediate execution |
| `/api/scheduler/jobs/{id}/pause` | POST | Pause without removing |
| `/api/scheduler/jobs/{id}/resume` | POST | Resume a paused job |
| `/api/scheduler/jobs/{id}/history` | GET | Get execution history |

## Available Scrapers

| Job ID | Default Interval | Description |
|--------|------------------|-------------|
| `cardhobby` | 30 min | CardHobby auctions (Chinese marketplace) |
| `goldin` | 30 min | Goldin Auctions |
| `fanatics` | 30 min | Fanatics Collect |
| `heritage` | 60 min | Heritage Auctions |
| `pristine` | 30 min | Pristine Auction |
| `cleanup` | 24 hours | Remove old ended auctions |

## How It Works

1. **Scheduler Service** (`app/services/scheduler.py`)
   - Uses APScheduler with AsyncIO
   - Singleton pattern - one scheduler per app
   - Jobs run in background, won't block API

2. **Scraper Jobs** (`app/services/scraper_jobs.py`)
   - Each job manages its own database session
   - Uses upsert logic: updates existing items, inserts new ones
   - Marks ended auctions automatically

3. **Price Updates**
   - Each scrape updates `current_bid` and `bid_count` for existing items
   - New items are inserted with full data
   - Items past their `end_time` are marked as "Ended"

## Example: Enable All Scrapers

```bash
# Enable all scrapers with default intervals
for job in cardhobby goldin fanatics heritage pristine cleanup; do
  curl -X POST "http://localhost:8000/api/scheduler/jobs/$job/enable"
done

# Check what's scheduled
curl http://localhost:8000/api/scheduler/status | jq
```

## Example: Custom Intervals

```bash
# CardHobby every 15 minutes (more frequent)
curl -X POST "http://localhost:8000/api/scheduler/jobs/cardhobby/enable?interval_minutes=15"

# Heritage every 2 hours (less frequent)
curl -X POST "http://localhost:8000/api/scheduler/jobs/heritage/enable?interval_minutes=120"
```

## Monitoring

Check job history:
```bash
curl http://localhost:8000/api/scheduler/jobs/cardhobby/history | jq
```

Response shows recent executions with status and any errors.

## Adding New Scrapers

1. Create scraper function in `app/services/scraper_jobs.py`:

```python
async def scrape_newscraper(max_items: int = 1000):
    """Scrape NewScraper auctions."""
    logger.info("Starting NewScraper scrape")
    # ... scraping logic ...
```

2. Add to `SCRAPER_JOBS` registry:

```python
SCRAPER_JOBS = {
    # ... existing jobs ...
    "newscraper": {
        "func": scrape_newscraper,
        "default_interval": 30,
        "description": "Scrape NewScraper auctions",
    },
}
```

3. The job will automatically be available via the API.

## Troubleshooting

**Jobs not running:**
- Check scheduler is running: `curl http://localhost:8000/api/scheduler/status`
- Check job is enabled and not paused
- Look at server logs for errors

**Database errors:**
- Each job creates its own session
- Check database file permissions
- Ensure database is initialized

**Rate limiting:**
- Jobs have built-in delays between API calls
- Adjust intervals if getting blocked
