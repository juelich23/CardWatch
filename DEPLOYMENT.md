# Production Deployment Guide

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Vercel        │     │   Railway/      │     │   PostgreSQL    │
│   (Frontend)    │────▶│   Render/Fly    │────▶│   (Supabase/    │
│   Next.js       │     │   (Backend)     │     │    Neon)        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │   Scheduler     │
                        │   (30 min jobs) │
                        └─────────────────┘
```

**Why this architecture:**
- Vercel excels at Next.js but serverless functions can't run scheduled jobs
- Backend needs a persistent process for the scheduler
- SQLite doesn't work in serverless (ephemeral filesystem)

---

## Phase 1: Database Migration (SQLite → PostgreSQL)

### Option A: Supabase (Recommended - Free tier available)
```bash
# 1. Create project at supabase.com
# 2. Get connection string from Settings > Database
# 3. Update .env
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
```

### Option B: Neon (Serverless PostgreSQL)
```bash
DATABASE_URL=postgresql+asyncpg://[USER]:[PASSWORD]@[HOST]/[DATABASE]?sslmode=require
```

### Backend Changes Needed:

1. **Install PostgreSQL driver:**
```bash
pip install asyncpg psycopg2-binary
```

2. **Update requirements.txt:**
```
asyncpg==0.29.0
psycopg2-binary==2.9.9
```

3. **Update app/config.py** - already supports DATABASE_URL env var

4. **Run migrations** to create tables in PostgreSQL

---

## Phase 2: Backend Deployment

### Option A: Railway (Recommended)

1. **Create railway.json:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

2. **Create Procfile:**
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

3. **Environment variables on Railway:**
```
DATABASE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=sk-ant-...
ENABLE_SCHEDULER=true
SECRET_KEY=<generate-random-key>
```

### Option B: Render

1. **Create render.yaml:**
```yaml
services:
  - type: web
    name: cardwatch-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: ENABLE_SCHEDULER
        value: true
```

### Option C: Fly.io

1. **Create fly.toml:**
```toml
app = "cardwatch-api"
primary_region = "ord"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8080"
  ENABLE_SCHEDULER = "true"

[http_service]
  internal_port = 8080
  force_https = true

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

---

## Phase 3: Frontend Deployment (Vercel)

### 1. Environment Variables

Create `.env.production` in frontend-nextjs:
```
NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
NEXT_PUBLIC_GRAPHQL_URL=https://your-backend-url.railway.app/graphql
```

### 2. Update API Client

Check `frontend-nextjs/lib/apollo-client.ts` uses environment variable:
```typescript
const httpLink = createHttpLink({
  uri: process.env.NEXT_PUBLIC_GRAPHQL_URL || 'http://localhost:8000/graphql',
});
```

### 3. Vercel Configuration

Create `vercel.json` in frontend-nextjs:
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "env": {
    "NEXT_PUBLIC_API_URL": "@api-url",
    "NEXT_PUBLIC_GRAPHQL_URL": "@graphql-url"
  }
}
```

### 4. Deploy to Vercel
```bash
cd frontend-nextjs
vercel --prod
```

---

## Phase 4: Pre-Deployment Checklist

### Backend
- [ ] Switch DATABASE_URL to PostgreSQL
- [ ] Run database migrations
- [ ] Test all scrapers work with new DB
- [ ] Set ENABLE_SCHEDULER=true
- [ ] Generate secure SECRET_KEY
- [ ] Configure CORS for production frontend URL
- [ ] Test GraphQL endpoint
- [ ] Test scheduler jobs run correctly

### Frontend
- [ ] Update API URLs for production
- [ ] Test build: `npm run build`
- [ ] Check no hardcoded localhost URLs
- [ ] Verify environment variables configured
- [ ] Test authentication flow

### Security
- [ ] API keys stored in environment variables (not code)
- [ ] CORS restricted to frontend domain only
- [ ] HTTPS enforced
- [ ] Rate limiting on API (optional but recommended)

---

## Phase 5: Migration Script

Create a script to migrate data from SQLite to PostgreSQL:

```python
# migrate_to_postgres.py
import sqlite3
import asyncio
import asyncpg

async def migrate():
    # Connect to SQLite
    sqlite_conn = sqlite3.connect('auction_data.db')
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(
        'postgresql://user:pass@host/db'
    )

    # Migrate auctions table
    sqlite_cursor.execute('SELECT * FROM auctions')
    auctions = sqlite_cursor.fetchall()
    # ... insert into PostgreSQL

    # Migrate auction_items table
    sqlite_cursor.execute('SELECT * FROM auction_items')
    items = sqlite_cursor.fetchall()
    # ... insert into PostgreSQL

    await pg_conn.close()
    sqlite_conn.close()

asyncio.run(migrate())
```

---

## Cost Estimates (Monthly)

| Service | Free Tier | Paid |
|---------|-----------|------|
| Vercel (Frontend) | Yes - generous | $20/mo Pro |
| Railway (Backend) | $5 credit | ~$5-10/mo |
| Supabase (Database) | 500MB free | $25/mo Pro |
| Neon (Database) | 512MB free | $19/mo |

**Estimated total: $0-30/month** depending on usage

---

## Quick Start Commands

```bash
# 1. Set up PostgreSQL (using Supabase)
# Go to supabase.com, create project, get connection string

# 2. Test backend with PostgreSQL locally
export DATABASE_URL="postgresql+asyncpg://..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# 3. Deploy backend to Railway
cd backend
railway login
railway init
railway up

# 4. Deploy frontend to Vercel
cd frontend-nextjs
vercel --prod
```

---

## Monitoring & Maintenance

### Health Checks
- Backend: `https://your-api.railway.app/health`
- Scheduler: `https://your-api.railway.app/api/scheduler/status`

### Logs
- Railway: `railway logs`
- Vercel: Dashboard > Deployments > Logs

### Database Backups
- Supabase: Automatic daily backups on paid plans
- Manual: `pg_dump` for local backups
